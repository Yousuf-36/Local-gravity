import { X, Shield, ShieldAlert, ShieldOff } from 'lucide-react';
import { useAppStore } from '../store';
import type { SafetyLevel } from '../types';

interface SafetyOption {
  level: SafetyLevel;
  label: string;
  description: string;
  icon: React.ReactNode;
  className: string;
}

const SAFETY_OPTIONS: SafetyOption[] = [
  {
    level: 'strict',
    label: 'Strict',
    description: 'All file writes and terminal commands require explicit approval.',
    icon: <ShieldAlert className="w-4 h-4" />,
    className: 'safety-strict',
  },
  {
    level: 'balanced',
    label: 'Balanced',
    description: 'File reads and safe commands run freely; destructive ops require approval.',
    icon: <Shield className="w-4 h-4" />,
    className: 'safety-balanced',
  },
  {
    level: 'off',
    label: 'Off',
    description: 'Agent runs all tools without interruption. Use only in sandboxed environments.',
    icon: <ShieldOff className="w-4 h-4" />,
    className: 'safety-off',
  },
];

/**
 * SettingsPanel — slide-in settings drawer mounted over the AgentPanel.
 *
 * Controlled by settingsPanelOpen in the store. Covers:
 *   - Safety level (strict / balanced / off) with per-option descriptions
 *   - Model selector (delegated to ModelSelector component)
 *
 * Persisted: safetyLevel survives page reload via Zustand persist middleware.
 */
export function SettingsPanel() {
  const { settingsPanelOpen, setSettingsPanelOpen, safetyLevel, setSafetyLevel } = useAppStore();

  if (!settingsPanelOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 overlay-fade-in"
        style={{ background: 'var(--overlay-bg)' }}
        onClick={() => setSettingsPanelOpen(false)}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className="fixed right-0 top-0 bottom-0 z-50 w-80 flex flex-col settings-slide-in"
        style={{
          background: 'var(--bg-surface)',
          borderLeft: '1px solid var(--border-default)',
          boxShadow: '-8px 0 32px rgba(0,0,0,0.5)',
        }}
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 h-11 border-b shrink-0"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Settings</h2>
          <button
            onClick={() => setSettingsPanelOpen(false)}
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1 rounded"
            aria-label="Close settings"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 py-5 space-y-6">
          {/* Safety Level */}
          <section>
            <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3">
              Safety Level
            </h3>
            <div className="space-y-2">
              {SAFETY_OPTIONS.map((opt) => {
                const isActive = safetyLevel === opt.level;
                return (
                  <button
                    key={opt.level}
                    onClick={() => setSafetyLevel(opt.level)}
                    className="w-full text-left px-3 py-2.5 rounded-lg border transition-all"
                    style={{
                      borderColor: isActive ? 'currentColor' : 'var(--border-default)',
                      background: isActive ? 'var(--bg-elevated)' : 'transparent',
                    }}
                    aria-pressed={isActive}
                  >
                    <div className={`flex items-center gap-2 mb-0.5 ${opt.className}`}>
                      {opt.icon}
                      <span className="text-xs font-semibold">{opt.label}</span>
                      {isActive && (
                        <span className="ml-auto text-[9px] font-mono uppercase tracking-wider opacity-70">
                          active
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-[var(--text-muted)] leading-relaxed pl-6">
                      {opt.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Info */}
          <section>
            <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3">
              About
            </h3>
            <div
              className="rounded-lg p-3 text-[11px] text-[var(--text-muted)] space-y-1 border"
              style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-elevated)' }}
            >
              <p><span className="text-[var(--text-secondary)]">LocalGravity</span> v0.2.0</p>
              <p>Runs 100% locally — no telemetry, no cloud.</p>
              <p>Agent model: set via the selector in the Agent panel header.</p>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
