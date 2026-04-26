import type { ToolCallFrame, ToolResultFrame } from '../types';
import { Terminal, FileText, List, Bot, CheckCircle, XCircle, Loader } from 'lucide-react';

interface Props {
  call: ToolCallFrame;
  result?: ToolResultFrame;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  read_file: <FileText className="w-3.5 h-3.5" />,
  write_file: <FileText className="w-3.5 h-3.5" />,
  run_terminal: <Terminal className="w-3.5 h-3.5" />,
  list_files: <List className="w-3.5 h-3.5" />,
  ollama_query: <Bot className="w-3.5 h-3.5" />,
};

function ArgPill({ k, v }: { k: string; v: string }) {
  const display = v.length > 60 ? `${v.slice(0, 60)}…` : v;
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded px-1.5 py-0.5 mr-1 mb-1">
      <span className="text-[var(--text-muted)]">{k}:</span>
      <span className="text-[var(--text-secondary)]">{display}</span>
    </span>
  );
}

/**
 * ToolCallCard — renders a single tool call event and its result (if available).
 * Shown inline in the AgentPanel message feed for every tool_call frame.
 */
export function ToolCallCard({ call, result }: Props) {
  const icon = TOOL_ICONS[call.tool] ?? <Bot className="w-3.5 h-3.5" />;
  const isDestructive = call.destructive;

  const statusIcon = result
    ? result.output.startsWith('<tool_result')
      ? <CheckCircle className="w-3.5 h-3.5 text-[var(--status-success)]" />
      : <XCircle className="w-3.5 h-3.5 text-[var(--status-error)]" />
    : <Loader className="w-3.5 h-3.5 animate-spin text-[var(--text-muted)]" />;

  const borderColor = isDestructive
    ? 'var(--status-warning)'
    : 'var(--border-default)';

  return (
    <div
      className="my-2 rounded-md border text-xs font-mono overflow-hidden"
      style={{ borderColor }}
    >
      {/* Header row */}
      <div
        className="flex items-center gap-2 px-3 py-1.5"
        style={{ background: isDestructive ? 'rgba(255,170,0,0.06)' : 'var(--bg-elevated)' }}
      >
        <span style={{ color: isDestructive ? 'var(--status-warning)' : 'var(--agent-primary)' }}>
          {icon}
        </span>
        <span className="font-semibold text-[var(--text-primary)]">{call.tool}</span>
        {isDestructive && (
          <span className="ml-1 px-1 py-0.5 rounded text-[9px] uppercase tracking-wider bg-[rgba(255,170,0,0.15)] text-[var(--status-warning)]">
            destructive
          </span>
        )}
        <span className="ml-auto">{statusIcon}</span>
      </div>

      {/* Args */}
      {Object.keys(call.args).length > 0 && (
        <div className="px-3 py-1.5 border-t border-[var(--border-subtle)] flex flex-wrap">
          {Object.entries(call.args)
            .filter(([k]) => k !== 'content') // content shown in DiffViewer
            .map(([k, v]) => (
              <ArgPill key={k} k={k} v={v} />
            ))}
        </div>
      )}

      {/* Result snippet */}
      {result && (
        <div className="px-3 py-1.5 border-t border-[var(--border-subtle)] bg-[var(--bg-base)]">
          <p className="text-[var(--text-muted)] leading-relaxed whitespace-pre-wrap break-all line-clamp-4">
            {result.output.replace(/<\/?tool_result[^>]*>/g, '').trim()}
          </p>
          {result.truncated && (
            <span className="text-[9px] text-[var(--text-muted)] italic">output truncated</span>
          )}
          {result.returncode !== undefined && (
            <span
              className="text-[10px] ml-2"
              style={{ color: result.returncode === 0 ? 'var(--status-success)' : 'var(--status-error)' }}
            >
              exit {result.returncode}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
