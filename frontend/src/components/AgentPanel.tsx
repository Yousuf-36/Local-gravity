import React, { useRef, useEffect, useState } from 'react';
import { useAgent, ChatMessage } from '../hooks/useAgent';
import { UI_STRINGS } from '../constants';
import { StatusBadge } from './StatusBadge';
import { StreamCursor } from './StreamCursor';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { SendHorizonal } from 'lucide-react';
import { useAppStore } from '../store';

function MessageBubble({ msg, isStreaming, isLast }: { msg: ChatMessage, isStreaming: boolean, isLast: boolean }) {
  const isAgent = msg.role === 'agent';
  
  if (!isAgent) {
    return (
      <div className="flex flex-col items-end mb-4">
        <div className="bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded px-3 py-2 max-w-[85%]">
          <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap">{msg.content}</p>
        </div>
      </div>
    );
  }

  // Parse markdown securely
  const getHtml = (markdown: string) => {
    return { __html: DOMPurify.sanitize(marked.parse(markdown, { async: false }) as string) };
  };

  return (
    <div className="mb-4 relative pl-3 py-2 rounded-r-md group"
      style={{ background: 'var(--agent-glow)', borderLeft: '2px solid var(--agent-primary)' }}>
      <span className="text-xs font-mono text-[var(--agent-primary)] mb-1 block">agent</span>
      <div 
        className="text-sm text-[var(--text-primary)] leading-relaxed prose prose-invert max-w-none prose-pre:bg-[var(--bg-base)] prose-pre:border prose-pre:border-[var(--border-subtle)] prose-code:text-[var(--text-code)]"
        dangerouslySetInnerHTML={getHtml(msg.content)}
      />
      {isLast && isStreaming && <StreamCursor />}
    </div>
  );
}

export function AgentPanel() {
  const { messages, error, isStreaming, sendMessage } = useAgent();
  const [inputVal, setInputVal] = useState('');
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (inputVal.trim() && !isStreaming) {
      sendMessage(inputVal);
      setInputVal('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-full w-full">
      {/* Header */}
      <div className="h-9 min-h-[36px] border-b border-[var(--border-subtle)] flex items-center justify-between px-3 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Agent</span>
          <span className="px-1.5 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[10px] font-mono text-[var(--text-secondary)]">gpt-oss:20b</span>
        </div>
        <StatusBadge status={isStreaming ? 'running' : 'idle'} />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col pt-6">
        {messages.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-[var(--text-muted)] select-none">
            <span className="text-4xl mb-4">✨</span>
            <p className="text-sm">Agent is ready.</p>
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <MessageBubble 
            key={msg.id} 
            msg={msg} 
            isStreaming={isStreaming} 
            isLast={idx === messages.length - 1} 
          />
        ))}

        {error && (
          <div className="mt-2 bg-[var(--status-error)] bg-opacity-10 border border-[var(--status-error)] rounded p-3 text-sm text-[var(--status-error)] mb-4">
            <span className="font-bold mb-1 block">Connectivity Error</span>
            {error}
          </div>
        )}
        <div ref={endOfMessagesRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--bg-base)] shrink-0">
        <form onSubmit={handleSubmit} className="relative">
          <textarea
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={UI_STRINGS.AGENT_PLACEHOLDER}
            disabled={isStreaming}
            className="w-full bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded-lg py-2 pl-3 pr-10 text-sm font-sans focus:outline-none focus:border-[var(--system-primary)] resize-none h-14 disabled:opacity-50 transition-colors"
          />
          <button
            type="submit"
            disabled={!inputVal.trim() || isStreaming}
            className="absolute right-2 bottom-3 text-[var(--system-primary)] disabled:text-[var(--text-muted)] hover:text-[var(--system-dim)] transition-colors p-1"
          >
            <SendHorizonal className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
