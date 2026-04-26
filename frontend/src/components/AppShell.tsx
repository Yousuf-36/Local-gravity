import { Settings } from 'lucide-react';
import { FileTree } from './FileTree';
import { EditorPane } from './EditorPane';
import { TabBar } from './TabBar';
import { AgentPanel } from './AgentPanel';
import { SettingsPanel } from './SettingsPanel';
import { useAppStore } from '../store';

/**
 * AppShell — top-level layout: sidebar | editor | agent panel.
 *
 * Phase 2 additions:
 *   - Settings gear icon (top-right of agent sidebar) calls toggleSettingsPanel
 *   - SettingsPanel overlay mounted at app root (covers full viewport right edge)
 *   - Gear icon visually highlights when panel is open
 */
export function AppShell() {
  const { settingsPanelOpen, toggleSettingsPanel } = useAppStore();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-base)] text-[var(--text-primary)] relative">
      {/* Left: File tree sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-[var(--border-subtle)] flex flex-col bg-[var(--bg-surface)]">
        <FileTree />
      </aside>

      {/* Center: Monaco editor */}
      <main className="flex-1 flex flex-col min-w-0 h-full relative">
        <TabBar />
        <EditorPane />
      </main>

      {/* Right: Agent panel */}
      <aside
        className="w-96 flex-shrink-0 border-l border-[var(--border-subtle)] flex flex-col bg-[var(--bg-surface)] relative"
      >
        {/* Settings gear — top-right corner of agent sidebar */}
        <button
          id="settings-gear-btn"
          onClick={toggleSettingsPanel}
          className="absolute top-2 right-2 z-10 p-1 rounded transition-colors"
          style={{
            color: settingsPanelOpen ? 'var(--agent-primary)' : 'var(--text-muted)',
          }}
          onMouseEnter={(e) => {
            if (!settingsPanelOpen)
              (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-primary)';
          }}
          onMouseLeave={(e) => {
            if (!settingsPanelOpen)
              (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)';
          }}
          aria-label={settingsPanelOpen ? 'Close settings' : 'Open settings'}
          aria-expanded={settingsPanelOpen}
          aria-controls="settings-panel"
          title="Settings"
        >
          <Settings
            className="w-3.5 h-3.5 transition-transform"
            style={{ transform: settingsPanelOpen ? 'rotate(45deg)' : 'none' }}
          />
        </button>

        <AgentPanel />
      </aside>

      {/* Settings overlay — mounted outside agent aside so it can cover the full right edge */}
      <SettingsPanel />
    </div>
  );
}
