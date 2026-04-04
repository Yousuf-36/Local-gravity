import { useState, useCallback, useEffect, useRef } from 'react';
import { agentApi } from '../api/agent';
import { useAppStore } from '../store';
import { UI_STRINGS } from '../constants';

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
}

export function useAgent() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { isAgentStreaming, setIsAgentStreaming } = useAppStore();
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const isComponentMounted = useRef(true);

  // Setup streaming listener only once
  useEffect(() => {
    isComponentMounted.current = true;
    unsubscribeRef.current = agentApi.onStream((chunk) => {
      if (!isComponentMounted.current) return;
      
      try {
        const payload = JSON.parse(chunk);
        
        if (payload.error) {
          setError(payload.message || UI_STRINGS.AGENT_ERROR_FALLBACK);
          setIsAgentStreaming(false);
          return;
        }

        const textContent = payload.message?.content || payload.content || '';
        if (textContent) {
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            if (lastMessage && lastMessage.role === 'agent') {
              lastMessage.content += textContent;
            } else {
              newMessages.push({ id: crypto.randomUUID(), role: 'agent', content: textContent });
            }
            return newMessages;
          });
        }
        
        if (payload.done) {
          setIsAgentStreaming(false);
        }
      } catch {
        // silently ignore malformed JSON chunks from the stream
      }
    });

    return () => {
      isComponentMounted.current = false;
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
    };
  }, [setIsAgentStreaming]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isAgentStreaming) return;

    setError(null);
    setIsAgentStreaming(true);
    
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: text },
      // add a placeholder for the agent response
      { id: crypto.randomUUID(), role: 'agent', content: '' }
    ]);

    try {
      await agentApi.sendMessage(text);
      // streaming is handled by the onStream effect above
    } catch (err) {
      setError(err instanceof Error ? err.message : UI_STRINGS.AGENT_ERROR_FALLBACK);
      setIsAgentStreaming(false);
      setMessages((prev) => {
        const resetMessages = [...prev];
        const lastMessage = resetMessages[resetMessages.length - 1];
        if (lastMessage.role === 'agent' && !lastMessage.content) {
          resetMessages.pop(); // remove empty agent bubble
        }
        return resetMessages;
      });
    }
  }, [isAgentStreaming, setIsAgentStreaming]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    error,
    isStreaming: isAgentStreaming,
    sendMessage,
    clearMessages
  };
}
