import { useEffect, useRef } from 'react';
import { X, Shield, ShieldAlert, ShieldOff, FolderOpen, ChevronRight } from 'lucide-react';
import { useAppStore } from '../store';
import { ModelSelector } from './ModelSelector';
import type { SafetyLevel } from '../types';

// ── Safety level option definitions ──────────────────────────────────────────

interface SafetyOption {
  level: SafetyLevel;
  label: string;
  description: string;
  tooltip: string;
  icon: React.ReactNode;
  cssClass: string;
}

const SAFETY_OPTIONS: SafetyOption[] = [
  {
    level: 'strict',
    label: 'Strict',
    description: 'All file writes and terminal commands require explicit approval.',
    tooltip:
      'Every destructive tool call (write_file, run_terminal) pauses the agent and shows an approval card. Nothing executes until you click Approve.',
    icon: <ShieldAlert className="w-4 h-4 shrink-0" />,
    cssClass: 'safety-strict',
  },
  {
    level: 'balanced',
    label: 'Balanced',
    description: 'Read operations and safe commands run freely; writes and terminals need approval.',
    tooltip:
      'read_file and list_files execute automatically. Only write_file and run_terminal trigger the approval gate.',
    icon: <Shield className="w-4 h-4 shrink-0" />,
    cssClass: 'safety-balanced',
  },
  {
    level: 'off',
    label: 'Off',
    description: 'Agent executes all tools without interruption.',
    tooltip:
      '⚠ No approval gate. The agent can write files and run commands freely. Use only in sandboxed or disposable environments.',
    icon: <ShieldOff className="w-4 h-4 shrink-0" />,
    cssClass: 'safety-off',
  },
];

// ── Tooltip ───────────────────────────────────────────────────────────────────

function Tooltip({ text }: { text: string }) {
  return (
    <span className="group relative ml-1.5 cursor-help">
      <span
        className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full text-[9px] font-bold border select-none"
        style={{
          borderColor: 'var(--border-strong)',
          color: 'var(--text-muted)',
        }}
      >
        ?
      </span>
      {/* Tooltip bubble */}
      <span
        className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 rounded-lg px-2.5 py-2 text-[10px] leading-relaxed opacity-0 group-hover:opacity-100 transition-opacity z-[60]"
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-default)',
          color: 'var(--text-secondary)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}
        role="tooltip"
      >
        {text}
        {/* Arrow */}
        <span
          className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent"
          style={{ borderTopColor: 'var(--border-default)' }}
        />
      </span>
    </span>
  );
}

// ── Section header ────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2.5 flex items-center gap-1">
      {children}
    </h3>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

/**
 * SettingsPanel — slide-in settings drawer.
 *
 * Features:
 *   - Closes on Escape key press
 *   - Closes on click outside (backdrop)
 *   - Workspace path picker (native folder dialog via Electron)
 *   - Model selector (live Ollama list, persisted via Zustand)
 *   - Safety level radio with tooltips for all three levels
 *   - Persisted: safetyLevel + selectedModel survive page reload
 */
export function SettingsPanel() {
  const {
    settingsPanelOpen,
    setSettingsPanelOpen,
    safetyLevel,
    setSafetyLevel,
    workspacePath,
    setWorkspacePath,
    setFileTree,
  } = useAppStore();

  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    if (!settingsPanelOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setSettingsPanelOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [settingsPanelOpen, setSettingsPanelOpen]);

  // Return focus to gear button on close
  useEffect(() => {
    if (!settingsPanelOpen) {
      (document.getElementById('settings-gear-btn') as HTMLButtonElement | null)?.focus();
    }
  }, [settingsPanelOpen]);

  const handleOpenFolder = async () => {
    try {
      const picked = await window.api.openFolder();
      if (picked) {
        setWorkspacePath(picked);
        setFileTree(null); // trigger refresh in FileTree
      }
    } catch {
      /* dialog cancelled or Electron unavailable */
    }
  };

  if (!settingsPanelOpen) return null;

  return (
    <>
      {/* Backdrop — click outside closes */}
      <div
        className="fixed inset-0 z-40 overlay-fade-in"
        style={{ background: 'var(--overlay-bg)' }}
        onClick={() => setSettingsPanelOpen(false)}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        ref={panelRef}
        className="fixed right-0 top-0 bottom-0 z-50 w-80 flex flex-col settings-slide-in"
        style={{
          background: 'var(--bg-surface)',
          borderLeft: '1px solid var(--border-default)',
          boxShadow: '-12px 0 40px rgba(0,0,0,0.55)',
        }}
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
      >
        {/* ── Header ───────────────────────────────────────────────────────── */}
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

        {/* ── Body ─────────────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto px-4 py-5 space-y-7">

          {/* Workspace */}
          <section>
            <SectionLabel>Workspace</SectionLabel>
            <button
              onClick={handleOpenFolder}
              className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border text-left transition-all hover:border-[var(--system-primary)] hover:bg-[var(--bg-elevated)] group"
              style={{ borderColor: 'var(--border-default)' }}
            >
              <FolderOpen className="w-4 h-4 text-[var(--system-primary)] shrink-0" />
              <span className="flex-1 min-w-0">
                {workspacePath ? (
                  <span className="block text-[11px] font-mono text-[var(--text-secondary)] truncate" title={workspacePath}>
                    {workspacePath}
                  </span>
                ) : (
                  <span className="text-xs text-[var(--text-muted)]">No folder open</span>
                )}
              </span>
              <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0 group-hover:text-[var(--system-primary)] transition-colors" />
            </button>
            <p className="text-[10px] text-[var(--text-muted)] mt-1.5 ml-0.5">
              Changes take effect immediately. The file tree will refresh.
            </p>
          </section>

          {/* Model */}
          <section>
            <SectionLabel>AI Model</SectionLabel>
            <div className="flex items-center gap-2">
              <ModelSelector />
              <span className="text-[10px] text-[var(--text-muted)]">
                Validated against Ollama /api/tags
              </span>
            </div>
          </section>

          {/* Safety Level */}
          <section>
            <SectionLabel>
              Safety Level
              <Tooltip text="Controls when the agent pauses to ask permission before executing a tool." />
            </SectionLabel>
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
                    {/* Row: icon + label + tooltip + active badge */}
                    <div className={`flex items-center gap-1.5 mb-0.5 ${opt.cssClass}`}>
                      {opt.icon}
                      <span className="text-xs font-semibold">{opt.label}</span>
                      <Tooltip text={opt.tooltip} />
                      {isActive && (
                        <span className="ml-auto text-[9px] font-mono uppercase tracking-wider opacity-70">
                          active
                        </span>
                      )}
                    </div>
                    {/* Description */}
                    <p className="text-[10px] text-[var(--text-muted)] leading-relaxed pl-6">
                      {opt.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </section>

          {/* About */}
          <section>
            <SectionLabel>About</SectionLabel>
            <div
              className="rounded-lg p-3 text-[11px] space-y-1 border"
              style={{
                borderColor: 'var(--border-subtle)',
                background: 'var(--bg-elevated)',
                color: 'var(--text-muted)',
              }}
            >
              <p>
                <span style={{ color: 'var(--text-secondary)' }}>LocalGravity</span>{' '}
                v0.2.0 — Phase 2
              </p>
              <p>Runs 100% locally. No telemetry, no cloud, no outbound traffic.</p>
              <p>
                Model validation is performed live against{' '}
                <code className="font-mono text-[var(--text-code)]">ollama /api/tags</code>
                {' '}at stream time.
              </p>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
