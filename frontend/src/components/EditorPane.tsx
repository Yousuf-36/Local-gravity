import { Editor } from '@monaco-editor/react';
import { useEditor } from '../hooks/useEditor';

const MONACO_OPTIONS = {
  theme: 'vs-dark',
  fontFamily: 'JetBrains Mono, monospace',
  fontSize: 13,
  lineHeight: 22,
  minimap: { enabled: false },
  renderLineHighlight: 'line' as const,
  scrollBeyondLastLine: false,
  smoothScrolling: true,
  cursorBlinking: 'smooth' as const,
  padding: { top: 12, bottom: 12 },
  overviewRulerBorder: false,
};

export function EditorPane() {
  const { activeTab, fileContents, loadingFiles, errorFiles } = useEditor();

  if (!activeTab) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[var(--editor-bg)]">
        <span className="text-4xl text-[var(--text-muted)] opacity-20 select-none">LocalGravity</span>
      </div>
    );
  }

  const isLoading = loadingFiles[activeTab];
  const error = errorFiles[activeTab];
  const content = fileContents[activeTab] || '';

  // Basic language mapping based on extension
  const getLanguage = (path: string) => {
    const ext = path.split('.').pop()?.toLowerCase();
    const map: Record<string, string> = {
      'ts': 'typescript', 'tsx': 'typescript',
      'js': 'javascript', 'jsx': 'javascript',
      'json': 'json', 'md': 'markdown',
      'html': 'html', 'css': 'css',
      'py': 'python', 'sh': 'shell'
    };
    return map[ext || ''] || 'plaintext';
  };

  return (
    <div className="flex-1 relative bg-[var(--editor-bg)]">
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-[var(--editor-bg)] bg-opacity-80">
          <span className="text-[var(--text-secondary)] font-mono text-sm animate-pulse">Loading {activeTab}...</span>
        </div>
      )}
      
      {error && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-[var(--editor-bg)]">
          <div className="text-[var(--status-error)] font-mono text-sm p-4 border border-[var(--status-error)] rounded bg-[var(--bg-surface)]">
            Error loading file: {error}
          </div>
        </div>
      )}
      
      {!isLoading && !error && (
        <Editor
          path={activeTab} // helps monaco resolve intellisense for cross-file if configured
          language={getLanguage(activeTab)}
          value={content}
          theme="vs-dark"
          options={MONACO_OPTIONS}
          className="w-full h-full"
        />
      )}
    </div>
  );
}
