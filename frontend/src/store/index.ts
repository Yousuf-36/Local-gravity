import { create } from 'zustand';
import { FileNode } from '../types';

interface AppState {
  // Global Workspace
  workspacePath: string | null;
  setWorkspacePath: (path: string | null) => void;

  // File Tree
  fileTree: FileNode | null;
  setFileTree: (tree: FileNode | null) => void;
  isFileTreeLoading: boolean;
  setIsFileTreeLoading: (isLoading: boolean) => void;
  fileTreeError: string | null;
  setFileTreeError: (error: string | null) => void;

  // Editor Tabs
  openTabs: string[]; // paths of open files
  activeTab: string | null;
  openTab: (path: string) => void;
  closeTab: (path: string) => void;
  setActiveTab: (path: string | null) => void;

  // Agent State
  isAgentStreaming: boolean;
  setIsAgentStreaming: (isStreaming: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Workspace
  workspacePath: null,
  setWorkspacePath: (path) => set({ workspacePath: path }),

  // File Tree
  fileTree: null,
  setFileTree: (tree) => set({ fileTree: tree }),
  isFileTreeLoading: false,
  setIsFileTreeLoading: (isLoading) => set({ isFileTreeLoading: isLoading }),
  fileTreeError: null,
  setFileTreeError: (error) => set({ fileTreeError: error }),

  // Editor
  openTabs: [],
  activeTab: null,
  openTab: (path) =>
    set((state) => {
      const tabs = new Set(state.openTabs);
      tabs.add(path);
      return { openTabs: Array.from(tabs), activeTab: path };
    }),
  closeTab: (path) =>
    set((state) => {
      const tabs = state.openTabs.filter((t) => t !== path);
      // If we close the active tab, select the last available tab or null
      const activeTab = state.activeTab === path ? (tabs[tabs.length - 1] || null) : state.activeTab;
      return { openTabs: tabs, activeTab };
    }),
  setActiveTab: (path) => set({ activeTab: path }),

  // Agent
  isAgentStreaming: false,
  setIsAgentStreaming: (isStreaming) => set({ isAgentStreaming: isStreaming }),
}));
