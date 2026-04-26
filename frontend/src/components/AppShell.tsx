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
 *   - Settings gear icon in the title bar (top-right of agent sidebar)
 *   - SettingsPanel overlay mounted at app root so it covers all panels
 */
export function AppShell() {
  const { settingsPanelOpen, setSettingsPanelOpen } = useAppStore();

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

      {/* Right: Agent panel + settings gear */}
      <aside className="w-96 flex-shrink-0 border-l border-[var(--border-subtle)] flex flex-col bg-[var(--bg-surface)] relative">
        {/* Gear icon — pinned to the top-right corner of the sidebar */}
        <button
          id="settings-gear-btn"
          onClick={() => setSettingsPanelOpen(!settingsPanelOpen)}
          className="absolute top-1.5 right-2 z-10 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1 rounded"
          aria-label="Open settings"
          title="Settings"
        >
          <Settings className="w-3.5 h-3.5" />
        </button>

        <AgentPanel />
      </aside>

      {/* Settings overlay — outside the sidebar so it can cover the full right edge */}
      <SettingsPanel />
    </div>
  );
}
