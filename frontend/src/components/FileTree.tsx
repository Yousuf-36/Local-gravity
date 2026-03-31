import { useState, useCallback } from 'react';
import { useFileTree } from '../hooks/useFileTree';
import { useEditor } from '../hooks/useEditor';
import { UI_STRINGS } from '../constants';
import { FolderOpen, File as FileIcon, ChevronRight, ChevronDown, Archive } from 'lucide-react';
import { FileNode } from '../types';

function FileTreeNode({ node, onFileClick }: { node: FileNode, onFileClick: (path: string) => void }) {
  const [isOpen, setIsOpen] = useState(false);
  
  const isDir = node.type === 'directory';
  
  const handleClick = () => {
    if (isDir) {
      setIsOpen(!isOpen);
    } else {
      onFileClick(node.path);
    }
  };

  return (
    <div className="select-none text-sm font-mono whitespace-nowrap">
      <div 
        onClick={handleClick}
        className="flex items-center gap-1.5 py-1 px-2 hover:bg-[var(--bg-hover)] cursor-pointer text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      >
        <span className="w-4 h-4 shrink-0 inline-flex items-center justify-center">
          {isDir ? (
            isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <span className="w-1" /> // indent for files without chevron
          )}
        </span>
        <span className="w-4 h-4 shrink-0 text-[var(--system-primary)]">
          {isDir ? (
            isOpen ? <FolderOpen className="w-3.5 h-3.5" /> : <Archive className="w-3.5 h-3.5" /> // using archive as closed folder proxy or folder
          ) : (
            <FileIcon className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          )}
        </span>
        <span className="truncate">{node.name}</span>
      </div>
      
      {isDir && isOpen && node.children && (
        <div className="pl-4 border-l border-[var(--border-subtle)] ml-[11px]">
          {node.children.map((child) => (
            <FileTreeNode key={child.path} node={child} onFileClick={onFileClick} />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileTree() {
  const { workspacePath, fileTree, isLoading, error, openWorkspace } = useFileTree();
  const { openFile } = useEditor();

  const handleFileClick = useCallback((path: string) => {
    openFile(path);
  }, [openFile]);

  return (
    <div className="flex flex-col h-full w-full">
      <div className="h-9 min-h-[36px] border-b border-[var(--border-subtle)] flex items-center justify-between px-3 bg-[var(--bg-elevated)] shrink-0">
        <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Explorer</span>
        <button 
          onClick={openWorkspace}
          className="text-[var(--system-primary)] hover:text-[var(--system-dim)] transition-colors p-1 rounded-sm text-xs font-medium focus:outline-none"
        >
          Open
        </button>
      </div>

      <div className="flex-1 overflow-y-auto overflow-x-auto p-1 py-2">
        {isLoading && (
          <div className="px-3 py-2 text-sm text-[var(--text-muted)] animate-pulse">Loading...</div>
        )}
        
        {error && (
          <div className="px-3 py-2 text-sm text-[var(--status-error)] break-words">
            {error}
          </div>
        )}
        
        {!workspacePath && !isLoading && !error && (
          <div className="flex flex-col items-center justify-center h-full px-4 text-center">
            <span className="text-sm text-[var(--text-secondary)] mb-4">{UI_STRINGS.NO_FOLDER_OPEN}</span>
            <button
              onClick={openWorkspace}
              className="bg-[var(--system-primary)] text-white px-3 py-1.5 rounded text-sm font-medium hover:bg-opacity-90 transition-opacity"
            >
              {UI_STRINGS.OPEN_FOLDER_BUTTON}
            </button>
          </div>
        )}

        {fileTree && !isLoading && (
          <FileTreeNode node={fileTree} onFileClick={handleFileClick} />
        )}
      </div>
    </div>
  );
}
