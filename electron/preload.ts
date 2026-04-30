/**
 * preload.ts — Runs in an isolated context between renderer and main process.
 * contextBridge.exposeInMainWorld is the ONLY way renderer JS touches Node/Electron APIs.
 * This surface is intentionally minimal — only what the UI genuinely needs.
 */
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('api', {
  // ── Agent ───────────────────────────────────────────────────────────────────
  /** Send a user message; the main process streams chunks back via onAgentStream. */
  sendAgentMessage: (msg: string): Promise<{ done: boolean }> =>
    ipcRenderer.invoke('agent:message', msg),

  /**
   * Register a callback for incoming agent stream chunks.
   * Returns an unsubscribe function.
   */
  onAgentStream: (cb: (chunk: string) => void): (() => void) => {
    const listener = (_: Electron.IpcRendererEvent, chunk: string) => cb(chunk)
    ipcRenderer.on('agent:stream', listener)
    return () => ipcRenderer.removeListener('agent:stream', listener)
  },

  /** Approve a pending destructive tool call (HITL gate). */
  approveToolCall: (taskId: string, callId: string): Promise<{ ok: boolean }> =>
    ipcRenderer.invoke('agent:approve', taskId, callId),

  /** Deny a pending destructive tool call (HITL gate). */
  denyToolCall: (taskId: string, callId: string): Promise<{ ok: boolean }> =>
    ipcRenderer.invoke('agent:deny', taskId, callId),

  // ── File System ─────────────────────────────────────────────────────────────
  /** Opens a native folder-picker dialog; persists the choice in electron-store. */
  openFolder: (): Promise<string | null> =>
    ipcRenderer.invoke('dialog:openFolder'),

  /** Read a file. Path must resolve within the open workspace or the call throws. */
  readFile: (filePath: string): Promise<string> =>
    ipcRenderer.invoke('fs:readFile', filePath),

  /** Write a file. Path must resolve within the open workspace or the call throws. */
  writeFile: (filePath: string, content: string): Promise<{ ok: boolean }> =>
    ipcRenderer.invoke('fs:writeFile', filePath, content),

  // ── Terminal ─────────────────────────────────────────────────────────────────
  /** Execute a command via the backend terminal sandbox (allowlist enforced server-side). */
  execCommand: (cmd: string): Promise<unknown> =>
    ipcRenderer.invoke('terminal:exec', cmd),

  /**
   * Stream terminal output lines.
   * Returns an unsubscribe function.
   */
  onTerminalOutput: (cb: (line: string) => void): (() => void) => {
    const listener = (_: Electron.IpcRendererEvent, line: string) => cb(line)
    ipcRenderer.on('terminal:output', listener)
    return () => ipcRenderer.removeListener('terminal:output', listener)
  },

  // ── Ollama ───────────────────────────────────────────────────────────────────
  /** Fetch the list of installed Ollama models from the backend. */
  listModels: (): Promise<string[]> => ipcRenderer.invoke('ollama:listModels'),

  /** Switch the active Ollama model (validated against allowlist server-side). */
  switchModel: (model: string): Promise<unknown> =>
    ipcRenderer.invoke('ollama:switchModel', model),
})
