import type { OllamaModel } from './index';

export interface ElectronAPI {
  // ── Agent ─────────────────────────────────────────────────────────────────
  /** Send a user message; chunks stream back via onAgentStream. */
  sendAgentMessage: (msg: string) => Promise<{ done: boolean }>;
  /** Register a callback for incoming agent stream chunks. Returns unsubscribe fn. */
  onAgentStream: (cb: (chunk: string) => void) => () => void;
  /** Approve a pending destructive tool call (HITL gate). */
  approveToolCall: (taskId: string, callId: string) => Promise<{ ok: boolean }>;
  /** Deny a pending destructive tool call (HITL gate). */
  denyToolCall: (taskId: string, callId: string) => Promise<{ ok: boolean }>;

  // ── File System ───────────────────────────────────────────────────────────
  /** Opens a native folder-picker dialog; persists choice in electron-store. */
  openFolder: () => Promise<string | null>;
  /** Read a file. Path must resolve within the open workspace. */
  readFile: (filePath: string) => Promise<string>;
  /** Write a file. Path must resolve within the open workspace. */
  writeFile: (filePath: string, content: string) => Promise<{ ok: boolean }>;

  // ── Terminal ──────────────────────────────────────────────────────────────
  /** Execute a command via the backend terminal sandbox (allowlist enforced). */
  execCommand: (cmd: string) => Promise<unknown>;
  /** Stream terminal output lines. Returns unsubscribe fn. */
  onTerminalOutput: (cb: (line: string) => void) => () => void;

  // ── Ollama ────────────────────────────────────────────────────────────────
  /** Fetch the list of installed Ollama models from the backend. */
  listModels: () => Promise<OllamaModel[]>;
  /** Switch the active Ollama model (validated against /api/tags server-side). */
  switchModel: (model: string) => Promise<unknown>;
}

declare global {
  interface Window {
    api: ElectronAPI;
  }
}
