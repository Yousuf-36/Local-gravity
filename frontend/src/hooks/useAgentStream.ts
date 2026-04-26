import { useEffect, useCallback, useRef } from 'react';
import { useAppStore } from '../store';
import type { AgentSSEFrame } from '../types';

/**
 * Parse a raw SSE `data:` line into a typed AgentSSEFrame.
 * Returns null if the line is not valid JSON or lacks a recognised `type`.
 */
function parseFrame(raw: string): AgentSSEFrame | null {
  // SSE lines arrive as `data: {json}` — strip the prefix
  const jsonStr = raw.startsWith('data: ') ? raw.slice(6) : raw;
  if (!jsonStr.trim()) return null;
  try {
    const obj = JSON.parse(jsonStr) as Record<string, unknown>;
    if (typeof obj.type !== 'string') return null;
    // Trust the discriminant — the backend guarantees the shape
    return obj as unknown as AgentSSEFrame;
  } catch {
    return null;
  }
}

/**
 * useAgentStream — subscribes to the Electron IPC agent stream and dispatches
 * every typed SSE frame into the Zustand store.
 *
 * This hook is mounted once at the AgentPanel level. It never returns data
 * directly; consumers read from the store.
 */
export function useAgentStream(): void {
  const {
    addAgentFrame,
    setPendingApproval,
    setIsAgentStreaming,
    setActiveTaskId,
  } = useAppStore();

  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;

    const unsubscribe = window.api.onAgentStream((chunk: string) => {
      if (!isMounted.current) return;

      const frame = parseFrame(chunk);
      if (!frame) return;

      // Always record the raw frame
      addAgentFrame(frame);

      switch (frame.type) {
        case 'plan':
          setIsAgentStreaming(true);
          setActiveTaskId(frame.task_id);
          break;

        case 'tool_call':
          // No state change needed; ToolCallCard reads from agentFrames
          break;

        case 'tool_result':
          // No state change needed; ToolCallCard reads from agentFrames
          break;

        case 'waiting_approval':
          setPendingApproval(frame);
          break;

        case 'final_answer':
          setIsAgentStreaming(false);
          setPendingApproval(null);
          break;

        case 'error':
          setIsAgentStreaming(false);
          setPendingApproval(null);
          break;
      }
    });

    return () => {
      isMounted.current = false;
      unsubscribe();
    };
  }, [addAgentFrame, setPendingApproval, setIsAgentStreaming, setActiveTaskId]);
}

/**
 * useSendAgentMessage — returns a stable callback to send a message to the
 * agent, resetting ephemeral state (frames, approval) before streaming begins.
 */
export function useSendAgentMessage(): (text: string) => Promise<void> {
  const { isAgentStreaming, setIsAgentStreaming, clearAgentFrames } = useAppStore();

  return useCallback(
    async (text: string) => {
      if (!text.trim() || isAgentStreaming) return;
      clearAgentFrames();
      setIsAgentStreaming(true);
      try {
        await window.api.sendAgentMessage(text);
      } catch (err) {
        setIsAgentStreaming(false);
        throw err;
      }
    },
    [isAgentStreaming, setIsAgentStreaming, clearAgentFrames],
  );
}
