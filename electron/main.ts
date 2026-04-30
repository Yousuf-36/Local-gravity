/**
 * main.ts — Electron application entry point.
 *
 * Security flags applied to BrowserWindow (ALL FOUR mandatory, never optional):
 *   nodeIntegration:             false  — renderer has zero Node.js access
 *   contextIsolation:            true   — preload runs in isolated context
 *   sandbox:                     true   — renderer process is OS-sandboxed
 *   webSecurity:                 true   — same-origin policy enforced
 *   allowRunningInsecureContent: false  — no mixed HTTP/HTTPS content
 *
 * All FastAPI communication originates here (main process → 127.0.0.1:8000).
 * The renderer never calls FastAPI directly.
 *
 * Production behaviour (NODE_ENV !== 'development'):
 *   - DevTools are never opened.
 *   - Backend is spawned from process.resourcesPath (packaged build).
 *   - Backend process is killed on app quit.
 */
import { app, BrowserWindow } from 'electron'
import path from 'path'
import { spawn, ChildProcess } from 'child_process'
import Store from 'electron-store'
import { applyCSP } from './security'
import { registerIpcHandlers } from './ipc'

const store = new Store<{ workspacePath: string }>()
let mainWindow: BrowserWindow | null = null
let backendProcess: ChildProcess | null = null

const isProd = process.env.NODE_ENV !== 'development'

// ── Backend spawn (packaged builds only) ─────────────────────────────────────

/**
 * Locate and spawn the bundled FastAPI backend when running as a packaged app.
 * In development the backend is started separately via `npm run dev:backend`.
 *
 * Layout inside the ASAR-excluded extraResources:
 *   <resourcesPath>/backend/          ← the entire backend/ folder
 *   <resourcesPath>/backend/.venv/    ← virtual-env bundled by electron-builder
 *
 * We look for the venv Python first; if absent we fall back to the system Python
 * that is expected to have uvicorn available (CI / developer machine).
 */
function spawnBackend(): void {
  if (!isProd) return // dev: backend is managed externally

  const resourcesPath = process.resourcesPath
  const backendDir = path.join(resourcesPath, 'backend')

  // Prefer the bundled virtual-env Python; fall back to system python
  const venvPython = process.platform === 'win32'
    ? path.join(backendDir, '.venv', 'Scripts', 'python.exe')
    : path.join(backendDir, '.venv', 'bin', 'python')

  const pythonExe = require('fs').existsSync(venvPython) ? venvPython : 'python'

  backendProcess = spawn(
    pythonExe,
    [
      '-m', 'uvicorn',
      'main:app',
      '--host', '127.0.0.1',
      '--port', '8000',
      '--log-level', 'warning',
    ],
    {
      cwd: backendDir,
      env: {
        ...process.env,
        // Signal the backend that it is running inside a packaged build
        PRODUCTION: 'true',
      },
      // Detach stdout/stderr from the Electron process so they don't block stdio
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )

  backendProcess.stdout?.on('data', (_data: Buffer) => {
    // Intentionally swallowed in prod — no console in packaged app
  })

  backendProcess.stderr?.on('data', (_data: Buffer) => {
    // Intentionally swallowed in prod
  })

  backendProcess.on('error', (_err: Error) => {
    // Backend failed to start — the UI will show connection-error state
  })
}

// ── Window ────────────────────────────────────────────────────────────────────

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0A0A0A',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      // ── SECURITY FLAGS — do not change these ──────────────────────────────
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      // ── preload — only contextBridge surface is exposed ───────────────────
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  // Apply CSP header to every renderer response
  applyCSP()

  // Register all IPC handlers (file, agent, terminal, ollama)
  registerIpcHandlers(mainWindow, store)

  // Load renderer — dev server in development, built bundle in production
  if (!isProd) {
    mainWindow.loadURL('http://localhost:5173')
    // DevTools only in development — never in packaged builds
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(
      path.join(__dirname, '..', 'frontend', 'dist', 'index.html'),
    )
    // DevTools explicitly disabled in production
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  spawnBackend()
  createWindow()
})

app.on('window-all-closed', () => {
  // macOS: keep process alive until Cmd-Q
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  // macOS: re-create window when dock icon is clicked and no windows are open
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

// Gracefully kill the backend when the app quits
app.on('quit', () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill('SIGTERM')
    backendProcess = null
  }
})

// Prevent navigation to external URLs (belt-and-suspenders against renderer exploits)
app.on('web-contents-created', (_, contents) => {
  contents.on('will-navigate', (event, url) => {
    const allowed = ['http://localhost:5173', 'app://localhost']
    if (!allowed.some((origin) => url.startsWith(origin))) {
      event.preventDefault()
    }
  })
  contents.setWindowOpenHandler(() => ({ action: 'deny' }))
})
