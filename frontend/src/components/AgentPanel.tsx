import { useRef, useEffect, useState, useCallback } from 'react';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { SendHorizonal } from 'lucide-react';

import { useAppStore } from '../store';
import { useAgentStream, useSendAgentMessage } from '../hooks/useAgentStream';
import { UI_STRINGS } from '../constants';
import { StatusBadge } from './StatusBadge';
import { StreamCursor } from './StreamCursor';
import { ToolCallCard } from './ToolCallCard';
import { ApprovalCard } from './ApprovalCard';
import { ModelSelector } from './ModelSelector';

import type {
  AgentSSEFrame,
  FinalAnswerFrame,
  PlanFrame,
  ToolCallFrame,
  ToolResultFrame,
  WaitingApprovalFrame,
} from '../types';

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderMarkdown(md: string): string {
  return DOMPurify.sanitize(marked.parse(md, { async: false }) as string);
}

// ── Sub-renderers per frame type ──────────────────────────────────────────────

function PlanBubble({ frame }: { frame: PlanFrame }) {
  return (
    <div className="mb-3 relative pl-3 py-2 rounded-r-md"
      style={{ background: 'var(--agent-glow)', borderLeft: '2px solid var(--agent-primary)' }}>
      <span className="text-[10px] font-mono text-[var(--agent-primary)] mb-1 block uppercase tracking-wider">plan</span>
      <div
        className="text-sm text-[var(--text-primary)] leading-relaxed prose prose-invert max-w-none prose-pre:bg-[var(--bg-base)] prose-code:text-[var(--text-code)]"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(frame.content) }}
      />
    </div>
  );
}

function FinalAnswerBubble({ frame, isStreaming }: { frame: FinalAnswerFrame; isStreaming: boolean }) {
  return (
    <div className="mb-4 relative pl-3 py-2 rounded-r-md group"
      style={{ background: 'var(--agent-glow)', borderLeft: '2px solid var(--agent-primary)' }}>
      <span className="text-[10px] font-mono text-[var(--agent-primary)] mb-1 block">
        agent · {frame.steps_used} step{frame.steps_used !== 1 ? 's' : ''}
      </span>
      <div
        className="text-sm text-[var(--text-primary)] leading-relaxed prose prose-invert max-w-none prose-pre:bg-[var(--bg-base)] prose-code:text-[var(--text-code)]"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(frame.content) }}
      />
      {isStreaming && <StreamCursor />}
    </div>
  );
}

function ErrorBubble({ message }: { message: string }) {
  return (
    <div className="my-2 bg-[var(--status-error)] bg-opacity-10 border border-[var(--status-error)] rounded p-3 text-sm text-[var(--status-error)] mb-4">
      <span className="font-bold mb-1 block">Agent Error</span>
      {message}
    </div>
  );
}

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex flex-col items-end mb-4">
      <div className="bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded px-3 py-2 max-w-[85%]">
        <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  );
}

// ── Frame renderer ────────────────────────────────────────────────────────────

function FrameRenderer({ frames }: { frames: AgentSSEFrame[] }) {
  // Build a map of call_id → { call, result } for ToolCallCards
  const toolMap = new Map<string, { call: ToolCallFrame; result?: ToolResultFrame }>();
  const orderedCallIds: string[] = [];

  for (const f of frames) {
    if (f.type === 'tool_call') {
      toolMap.set(f.call_id, { call: f });
      orderedCallIds.push(f.call_id);
    } else if (f.type === 'tool_result') {
      const entry = toolMap.get(f.call_id);
      if (entry) entry.result = f;
    }
  }

  return (
    <>
      {frames.map((frame, idx) => {
        switch (frame.type) {
          case 'plan':
            return <PlanBubble key={idx} frame={frame} />;
          case 'tool_call':
            return (
              <ToolCallCard
                key={frame.call_id}
                call={frame}
                result={toolMap.get(frame.call_id)?.result}
              />
            );
          case 'tool_result':
            // Already rendered inside ToolCallCard — skip standalone
            return null;
          case 'final_answer':
            return <FinalAnswerBubble key={idx} frame={frame} isStreaming={false} />;
          case 'error':
            return <ErrorBubble key={idx} message={frame.message} />;
          case 'waiting_approval':
            // ApprovalCard is rendered separately at panel level
            return null;
          default:
            return null;
        }
      })}
    </>
  );
}

// ── Main Panel ────────────────────────────────────────────────────────────────

export function AgentPanel() {
  const { isAgentStreaming, agentFrames, pendingApproval } = useAppStore();
  const [inputVal, setInputVal] = useState('');
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const [userMessages, setUserMessages] = useState<string[]>([]);

  // Mount the stream subscriber
  useAgentStream();
  const sendMessage = useSendAgentMessage();

  // Auto-scroll
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [agentFrames, pendingApproval]);

  const handleSubmit = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();
      const text = inputVal.trim();
      if (!text || isAgentStreaming) return;
      setInputVal('');
      setError(null);
      setUserMessages((prev) => [...prev, text]);
      try {
        await sendMessage(text);
      } catch (err) {
        setError(err instanceof Error ? err.message : UI_STRINGS.AGENT_ERROR_FALLBACK);
      }
    },
    [inputVal, isAgentStreaming, sendMessage],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Interleave user messages with agent frames (simple assumption: one user turn)
  const hasContent = userMessages.length > 0 || agentFrames.length > 0;

  return (
    <div className="flex flex-col h-full w-full">
      {/* Header */}
      <div className="h-9 min-h-[36px] border-b border-[var(--border-subtle)] flex items-center justify-between px-3 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Agent</span>
          <ModelSelector />
        </div>
        <StatusBadge status={isAgentStreaming ? 'running' : 'idle'} />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col pt-4">
        {!hasContent && (
          <div className="flex-1 flex flex-col items-center justify-center text-[var(--text-muted)] select-none">
            <span className="text-4xl mb-4">✨</span>
            <p className="text-sm">Agent is ready.</p>
          </div>
        )}

        {/* User messages interleaved with frames */}
        {userMessages.map((msg, i) => (
          <UserBubble key={i} content={msg} />
        ))}

        {/* Agent SSE frames */}
        <FrameRenderer frames={agentFrames} />

        {/* HITL approval gate */}
        {pendingApproval && (
          <ApprovalCard frame={pendingApproval as WaitingApprovalFrame} />
        )}

        {/* Error display */}
        {error && <ErrorBubble message={error} />}

        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--bg-base)] shrink-0">
        <form onSubmit={handleSubmit} className="relative">
          <textarea
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={UI_STRINGS.AGENT_PLACEHOLDER}
            disabled={isAgentStreaming}
            className="w-full bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded-lg py-2 pl-3 pr-10 text-sm font-sans focus:outline-none focus:border-[var(--system-primary)] resize-none h-14 disabled:opacity-50 transition-colors"
          />
          <button
            type="submit"
            disabled={!inputVal.trim() || isAgentStreaming}
            className="absolute right-2 bottom-3 text-[var(--system-primary)] disabled:text-[var(--text-muted)] hover:text-[var(--system-dim)] transition-colors p-1"
          >
            <SendHorizonal className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
