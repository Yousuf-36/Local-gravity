import { FileTree } from './FileTree';
import { EditorPane } from './EditorPane';
import { TabBar } from './TabBar';
import { AgentPanel } from './AgentPanel';

export function AppShell() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-base)] text-[var(--text-primary)]">
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
      <aside className="w-96 flex-shrink-0 border-l border-[var(--border-subtle)] flex flex-col bg-[var(--bg-surface)]">
        <AgentPanel />
      </aside>
    </div>
  );
}
