import { useState } from 'react';
import { ShieldAlert, CheckCircle, XCircle, Terminal, FileText } from 'lucide-react';
import type { WaitingApprovalFrame } from '../types';
import { useAppStore } from '../store';

interface Props {
  frame: WaitingApprovalFrame;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  write_file: <FileText className="w-4 h-4" />,
  run_terminal: <Terminal className="w-4 h-4" />,
};

/**
 * ApprovalCard — rendered when the executor emits a `waiting_approval` frame.
 *
 * Shows what the agent wants to do (tool + args + human-readable summary) and
 * presents Approve / Deny buttons. On decision, calls the Electron IPC bridge
 * which POSTs to /agent/approve or /agent/deny, unblocking the executor loop.
 */
export function ApprovalCard({ frame }: Props) {
  const { setPendingApproval } = useAppStore();
  const [status, setStatus] = useState<'pending' | 'approving' | 'denying' | 'done'>('pending');

  const icon = TOOL_ICONS[frame.tool] ?? <ShieldAlert className="w-4 h-4" />;

  const handleApprove = async () => {
    setStatus('approving');
    try {
      await window.api.approveToolCall(frame.task_id, frame.call_id);
    } catch {
      // Backend will emit an error frame; we just clear the card
    } finally {
      setStatus('done');
      setPendingApproval(null);
    }
  };

  const handleDeny = async () => {
    setStatus('denying');
    try {
      await window.api.denyToolCall(frame.task_id, frame.call_id);
    } catch {
      // Backend will halt the executor regardless
    } finally {
      setStatus('done');
      setPendingApproval(null);
    }
  };

  if (status === 'done') return null;

  const isLoading = status === 'approving' || status === 'denying';

  return (
    <div
      className="my-3 rounded-lg border overflow-hidden shadow-lg"
      style={{
        borderColor: 'var(--status-warning)',
        background: 'rgba(255, 170, 0, 0.04)',
        boxShadow: '0 0 24px rgba(255, 170, 0, 0.08)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-2.5 border-b"
        style={{ borderColor: 'var(--status-warning)', background: 'rgba(255,170,0,0.1)' }}
      >
        <ShieldAlert className="w-4 h-4 shrink-0" style={{ color: 'var(--status-warning)' }} />
        <span className="text-sm font-semibold" style={{ color: 'var(--status-warning)' }}>
          Approval Required
        </span>
      </div>

      {/* Body */}
      <div className="px-4 py-3 space-y-3">
        {/* Tool + summary */}
        <div className="flex items-start gap-2">
          <span className="mt-0.5 text-[var(--text-muted)]">{icon}</span>
          <div>
            <p className="text-xs font-mono font-semibold text-[var(--text-primary)]">
              {frame.tool}
            </p>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">{frame.summary}</p>
          </div>
        </div>

        {/* Args (excluding large content blobs) */}
        {Object.entries(frame.args).filter(([k]) => k !== 'content').length > 0 && (
          <div className="space-y-1">
            {Object.entries(frame.args)
              .filter(([k]) => k !== 'content')
              .map(([k, v]) => (
                <div key={k} className="flex items-baseline gap-2 text-xs font-mono">
                  <span className="text-[var(--text-muted)] shrink-0">{k}:</span>
                  <span className="text-[var(--text-secondary)] break-all">{v}</span>
                </div>
              ))}
          </div>
        )}

        {/* Content preview for write_file */}
        {frame.args.content && (
          <pre
            className="text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded p-2 overflow-x-auto max-h-32 leading-relaxed"
          >
            {frame.args.content.slice(0, 500)}
            {frame.args.content.length > 500 && '\n… (truncated)'}
          </pre>
        )}

        {/* Buttons */}
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={handleApprove}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition-all disabled:opacity-50"
            style={{
              background: 'rgba(0,200,100,0.15)',
              border: '1px solid var(--status-success)',
              color: 'var(--status-success)',
            }}
          >
            <CheckCircle className="w-3.5 h-3.5" />
            {status === 'approving' ? 'Approving…' : 'Approve'}
          </button>
          <button
            onClick={handleDeny}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition-all disabled:opacity-50"
            style={{
              background: 'rgba(255,60,60,0.12)',
              border: '1px solid var(--status-error)',
              color: 'var(--status-error)',
            }}
          >
            <XCircle className="w-3.5 h-3.5" />
            {status === 'denying' ? 'Denying…' : 'Deny'}
          </button>
        </div>
      </div>
    </div>
  );
}
