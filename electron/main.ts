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
 */
import { app, BrowserWindow } from 'electron'
import path from 'path'
import Store from 'electron-store'
import { applyCSP } from './security'
import { registerIpcHandlers } from './ipc'

const store = new Store<{ workspacePath: string }>()
let mainWindow: BrowserWindow | null = null

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
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(
      path.join(__dirname, '..', 'frontend', 'dist', 'index.html'),
    )
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  // macOS: keep process alive until Cmd-Q
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  // macOS: re-create window when dock icon is clicked and no windows are open
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
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
