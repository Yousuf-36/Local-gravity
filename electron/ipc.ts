/**
 * ipc.ts — All ipcMain handlers in one place.
 * Kept separate from main.ts so neither file exceeds 200 lines.
 *
 * Security contract:
 *   - Every handler validates input types before use
 *   - File operations delegate to assertWithinWorkspace()
 *   - Terminal commands delegate to the backend allowlist (never exec locally)
 *   - Agent streaming proxies through fetch() — renderer never reaches FastAPI directly
 */
import { BrowserWindow, dialog, ipcMain } from 'electron'
import fs from 'fs/promises'
import path from 'path'
import Store from 'electron-store'
import { assertWithinWorkspace } from './security'

const BACKEND = 'http://127.0.0.1:8000'
const DEFAULT_MODEL = 'gpt-oss:20b'

type AppStore = Store<{ workspacePath: string }>

export function registerIpcHandlers(win: BrowserWindow, store: AppStore): void {
  // ── dialog:openFolder ──────────────────────────────────────────────────────
  ipcMain.handle('dialog:openFolder', async () => {
    const result = await dialog.showOpenDialog(win, {
      properties: ['openDirectory'],
    })
    if (!result.canceled && result.filePaths.length > 0) {
      store.set('workspacePath', result.filePaths[0])
      return result.filePaths[0]
    }
    return null
  })

  // ── fs:readFile ────────────────────────────────────────────────────────────
  ipcMain.handle('fs:readFile', async (_, filePath: unknown) => {
    if (typeof filePath !== 'string') throw new Error('fs:readFile — path must be a string')
    const workspace = store.get('workspacePath', '')
    assertWithinWorkspace(filePath, workspace)
    return fs.readFile(path.resolve(filePath), 'utf-8')
  })

  // ── fs:writeFile ───────────────────────────────────────────────────────────
  ipcMain.handle('fs:writeFile', async (_, filePath: unknown, content: unknown) => {
    if (typeof filePath !== 'string') throw new Error('fs:writeFile — path must be a string')
    if (typeof content !== 'string') throw new Error('fs:writeFile — content must be a string')
    const workspace = store.get('workspacePath', '')
    assertWithinWorkspace(filePath, workspace)
    const resolved = path.resolve(filePath)
    await fs.mkdir(path.dirname(resolved), { recursive: true })
    await fs.writeFile(resolved, content, 'utf-8')
    return { ok: true }
  })

  // ── terminal:exec ──────────────────────────────────────────────────────────
  // Type + length validated here; allowlist/denylist enforced in the Python backend.
  ipcMain.handle('terminal:exec', async (_, cmd: unknown) => {
    if (typeof cmd !== 'string' || cmd.length > 2000) {
      throw new Error('terminal:exec — invalid command type or length > 2000 chars')
    }
    const workspace = store.get('workspacePath', '')
    const res = await fetch(`${BACKEND}/terminal/exec`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: cmd, workspace }),
    })
    if (!res.ok) {
      const err = (await res.json()) as { error?: string }
      throw new Error(err.error ?? 'Terminal execution failed')
    }
    return res.json()
  })

  // ── agent:message ──────────────────────────────────────────────────────────
  // Initiates an SSE stream from the backend and forwards chunks to the renderer.
  ipcMain.handle('agent:message', async (_, msg: unknown) => {
    if (typeof msg !== 'string' || msg.length > 32_000) {
      throw new Error('agent:message — invalid message type or length > 32000 chars')
    }
    const workspace = store.get('workspacePath', '')
    const res = await fetch(`${BACKEND}/agent/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        model: DEFAULT_MODEL,
        workspace_path: workspace,
        session_id: 'default',
      }),
    })
    if (!res.body) throw new Error('No response body from agent stream')
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      win.webContents.send('agent:stream', chunk)
    }
    return { done: true }
  })

  // ── agent:approve ──────────────────────────────────────────────────────────
  // Unblocks a pending HITL approval gate in the executor.
  ipcMain.handle('agent:approve', async (_, taskId: unknown, callId: unknown) => {
    if (typeof taskId !== 'string' || typeof callId !== 'string') {
      throw new Error('agent:approve — taskId and callId must be strings')
    }
    const res = await fetch(`${BACKEND}/agent/approve/${taskId}/${callId}`, {
      method: 'POST',
    })
    if (!res.ok) {
      const err = (await res.json()) as { detail?: string }
      throw new Error(err.detail ?? 'agent:approve — backend request failed')
    }
    return res.json()
  })

  // ── agent:deny ─────────────────────────────────────────────────────────────
  // Rejects a pending HITL approval gate — executor emits error frame and halts.
  ipcMain.handle('agent:deny', async (_, taskId: unknown, callId: unknown) => {
    if (typeof taskId !== 'string' || typeof callId !== 'string') {
      throw new Error('agent:deny — taskId and callId must be strings')
    }
    const res = await fetch(`${BACKEND}/agent/deny/${taskId}/${callId}`, {
      method: 'POST',
    })
    if (!res.ok) {
      const err = (await res.json()) as { detail?: string }
      throw new Error(err.detail ?? 'agent:deny — backend request failed')
    }
    return res.json()
  })

  ipcMain.handle('ollama:listModels', async () => {
    const res = await fetch(`${BACKEND}/ollama/models`)
    if (!res.ok) throw new Error('ollama:listModels — backend request failed')
    return res.json()
  })

  // ── ollama:switchModel ─────────────────────────────────────────────────────
  ipcMain.handle('ollama:switchModel', async (_, model: unknown) => {
    if (typeof model !== 'string') throw new Error('ollama:switchModel — model must be a string')
    const res = await fetch(`${BACKEND}/ollama/switch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
    })
    if (!res.ok) {
      const err = (await res.json()) as { error?: string }
      throw new Error(err.error ?? 'Model switch failed')
    }
    return res.json()
  })
}
