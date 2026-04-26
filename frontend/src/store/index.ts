import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AgentSSEFrame, FileNode, OllamaModel, SafetyLevel, WaitingApprovalFrame } from '../types';

// ── Persisted slice (survives page reload) ────────────────────────────────────
interface PersistedState {
  selectedModel: string;
  safetyLevel: SafetyLevel;
}

// ── Full app state ────────────────────────────────────────────────────────────
interface AppState extends PersistedState {
  // ── Workspace ───────────────────────────────────────────────────────────────
  workspacePath: string | null;
  setWorkspacePath: (path: string | null) => void;

  // ── File Tree ────────────────────────────────────────────────────────────────
  fileTree: FileNode | null;
  setFileTree: (tree: FileNode | null) => void;
  isFileTreeLoading: boolean;
  setIsFileTreeLoading: (loading: boolean) => void;
  fileTreeError: string | null;
  setFileTreeError: (error: string | null) => void;

  // ── Editor Tabs ──────────────────────────────────────────────────────────────
  openTabs: string[];
  activeTab: string | null;
  openTab: (path: string) => void;
  closeTab: (path: string) => void;
  setActiveTab: (path: string | null) => void;

  // ── Agent Streaming ──────────────────────────────────────────────────────────
  isAgentStreaming: boolean;
  setIsAgentStreaming: (streaming: boolean) => void;

  activeTaskId: string | null;
  setActiveTaskId: (id: string | null) => void;

  /** Ordered list of all SSE frames received for the current task. */
  agentFrames: AgentSSEFrame[];
  addAgentFrame: (frame: AgentSSEFrame) => void;
  clearAgentFrames: () => void;

  /** Non-null when the executor is waiting for HITL approval. */
  pendingApproval: WaitingApprovalFrame | null;
  setPendingApproval: (frame: WaitingApprovalFrame | null) => void;

  // ── Ollama / Model ───────────────────────────────────────────────────────────
  availableModels: OllamaModel[];
  setAvailableModels: (models: OllamaModel[]) => void;
  setSelectedModel: (model: string) => void;

  // ── Settings ─────────────────────────────────────────────────────────────────
  settingsPanelOpen: boolean;
  setSettingsPanelOpen: (open: boolean) => void;
  setSafetyLevel: (level: SafetyLevel) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // ── Workspace ─────────────────────────────────────────────────────────────
      workspacePath: null,
      setWorkspacePath: (path) => set({ workspacePath: path }),

      // ── File Tree ─────────────────────────────────────────────────────────────
      fileTree: null,
      setFileTree: (tree) => set({ fileTree: tree }),
      isFileTreeLoading: false,
      setIsFileTreeLoading: (loading) => set({ isFileTreeLoading: loading }),
      fileTreeError: null,
      setFileTreeError: (error) => set({ fileTreeError: error }),

      // ── Editor ────────────────────────────────────────────────────────────────
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
          const activeTab =
            state.activeTab === path
              ? (tabs[tabs.length - 1] ?? null)
              : state.activeTab;
          return { openTabs: tabs, activeTab };
        }),
      setActiveTab: (path) => set({ activeTab: path }),

      // ── Agent ─────────────────────────────────────────────────────────────────
      isAgentStreaming: false,
      setIsAgentStreaming: (streaming) => set({ isAgentStreaming: streaming }),

      activeTaskId: null,
      setActiveTaskId: (id) => set({ activeTaskId: id }),

      agentFrames: [],
      addAgentFrame: (frame) =>
        set((state) => ({ agentFrames: [...state.agentFrames, frame] })),
      clearAgentFrames: () =>
        set({ agentFrames: [], pendingApproval: null, activeTaskId: null }),

      pendingApproval: null,
      setPendingApproval: (frame) => set({ pendingApproval: frame }),

      // ── Ollama ────────────────────────────────────────────────────────────────
      availableModels: [],
      setAvailableModels: (models) => set({ availableModels: models }),
      selectedModel: 'llama3',
      setSelectedModel: (model) => set({ selectedModel: model }),

      // ── Settings ──────────────────────────────────────────────────────────────
      settingsPanelOpen: false,
      setSettingsPanelOpen: (open) => set({ settingsPanelOpen: open }),
      safetyLevel: 'strict',
      setSafetyLevel: (level) => set({ safetyLevel: level }),
    }),
    {
      name: 'localgravity-store',
      // Only persist user preferences — not ephemeral streaming state
      partialize: (state): PersistedState => ({
        selectedModel: state.selectedModel,
        safetyLevel: state.safetyLevel,
      }),
    },
  ),
);
