import { AgentStatus } from '../types';

interface StatusBadgeProps {
  status: AgentStatus;
}

const statusConfig: Record<AgentStatus, { color: string; label: string; dot: boolean }> = {
  idle: { color: 'var(--text-muted)', label: 'idle', dot: false },
  running: { color: 'var(--status-running)', label: 'running', dot: true },
  executing: { color: 'var(--status-running)', label: 'executing', dot: true },
  planning: { color: 'var(--status-warning)', label: 'planning', dot: true },
  verifying: { color: 'var(--status-success)', label: 'verifying', dot: true },
  done: { color: 'var(--status-success)', label: 'done', dot: false },
  error: { color: 'var(--status-error)', label: 'error', dot: false },
  waiting_approval: { color: 'var(--agent-primary)', label: 'waiting', dot: true },
};

export function StatusBadge({ status }: StatusBadgeProps) {
  // Map our UI states back if there's an exact mismatch, though types align.
  const cfg = statusConfig[status] || statusConfig.idle;
  
  return (
    <span 
      className="flex items-center gap-1.5 text-[10px] font-mono px-2 py-0.5 rounded capitalize"
      style={{ color: cfg.color, background: `${cfg.color}18` }}
    >
      {cfg.dot && (
        <span 
          className="w-1.5 h-1.5 rounded-full animate-pulse"
          style={{ background: cfg.color }} 
        />
      )}
      {cfg.label}
    </span>
  );
}
