import { useEditor } from '../hooks/useEditor';
import { X, Circle } from 'lucide-react';

export function TabBar() {
  const { openTabs, activeTab, setActiveTab, closeFile } = useEditor();

  if (openTabs.length === 0) {
    return <div className="h-9 border-b border-[var(--border-subtle)] bg-[var(--bg-base)]" />;
  }

  return (
    <div className="flex h-9 border-b border-[var(--border-subtle)] bg-[var(--bg-base)] overflow-x-auto overflow-y-hidden select-none">
      {openTabs.map((path) => {
        const isActive = activeTab === path;
        const filename = path.split(/[/\\]/).pop() || path;
        // Mock dirty state for now
        const isDirty = false;

        return (
          <div
            key={path}
            onClick={() => setActiveTab(path)}
            className={`flex items-center gap-2 px-3 py-1 cursor-pointer border-r border-[var(--border-subtle)] min-w-[120px] max-w-[200px] transition-colors
              ${isActive ? 'bg-[var(--bg-selected)] text-[var(--text-primary)] border-t border-t-[var(--system-primary)]' : 'text-[var(--text-secondary)] hover:bg-[var(--bg-surface)] border-t border-t-transparent'}`}
          >
            <span className="text-xs font-mono truncate flex-1" title={path}>
              {filename}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                closeFile(path);
              }}
              className="p-0.5 rounded-sm hover:bg-[var(--bg-hover)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors inline-flex items-center justify-center shrink-0 w-4 h-4"
              aria-label={`Close ${filename}`}
            >
              {isDirty ? (
                <Circle className="w-2 h-2 fill-current" />
              ) : (
                <X className="w-3 h-3" />
              )}
            </button>
          </div>
        );
      })}
    </div>
  );
}
