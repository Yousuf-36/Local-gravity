# LocalGravity

A local-first, privacy-first agentic IDE. No cloud APIs, no telemetry — everything runs on your machine, powered by [Ollama](https://ollama.ai).

Built with **Electron** · **FastAPI** · **React** · **Ollama (GPT-OSS 20B)**

---

## What it is

LocalGravity is a desktop IDE that puts an AI coding agent next to your editor. The agent can read files, write code, and run sandboxed terminal commands — all without a single byte leaving your machine.

```
[File Tree] │ [Monaco Editor] │ [Agent Chat]
```

---

## Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron 33 (sandboxed renderer, contextBridge IPC) |
| AI backend | FastAPI + Uvicorn (bound to 127.0.0.1 only) |
| Local model | Ollama — `gpt-oss:20b` |
| Frontend | React + Vite + TypeScript + TailwindCSS |
| Editor | Monaco Editor (VS Code engine) |

---

## Requirements

- [Node.js](https://nodejs.org) 20+
- [Python](https://python.org) 3.12+
- [Ollama](https://ollama.ai) installed and running (`ollama serve`)
- The `gpt-oss:20b` model pulled: `ollama pull gpt-oss:20b`

---

## Getting started

### 1. Clone

```bash
git clone https://github.com/Yousuf-36/Local-gravity.git
cd Local-gravity
```

### 2. Install dependencies

```bash
# Root + Electron + Frontend
npm run install:all

# Python backend
cd backend
pip install -r requirements.txt
cd ..
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env if you need to change OLLAMA_HOST or WORKSPACE_ROOT
```

### 4. Start everything

```bash
npm run dev
```

This starts three processes concurrently:
- **Electron** shell (TypeScript → `dist/`, then `electron .`)
- **Vite** dev server for the React frontend on `http://localhost:5173`
- **Uvicorn** FastAPI backend on `http://127.0.0.1:8000`

---

## Security model

LocalGravity is built security-first from the ground up:

| Threat | Defence |
|---|---|
| Renderer ↔ Node.js access | `nodeIntegration: false`, `contextIsolation: true`, `sandbox: true` |
| External network calls | CSP `connect-src` locked to `127.0.0.1:8000` only |
| Path traversal | `safe_resolve()` on every file operation server-side |
| Command injection | `validate_command()` — explicit ALLOWLIST + DENYLIST + pattern regex |
| Prompt injection via files | File content wrapped in `<file_content>` tags before model sees it |
| Agent HTML output | Rendered via `DOMPurify + marked` — never raw `innerHTML` |

The FastAPI backend only ever binds to `127.0.0.1`. It is not reachable from any other network interface.

---

## Project structure

```
localgravity/
├── electron/           # Electron main process (TypeScript)
│   ├── main.ts         # BrowserWindow, app lifecycle
│   ├── preload.ts      # contextBridge IPC surface
│   ├── ipc.ts          # All IPC handlers
│   └── security.ts     # CSP injection, path validation
├── frontend/           # React renderer (Vite + TypeScript)
│   └── src/
│       ├── components/ # AppShell, FileTree, EditorPane, AgentPanel ...
│       ├── hooks/
│       └── store/
├── backend/            # FastAPI Python backend
│   ├── main.py
│   ├── config.py
│   ├── routers/        # agent, files, terminal, ollama
│   ├── agents/         # streamer, orchestrator
│   ├── security/       # terminal sandbox
│   └── models/         # Pydantic schemas
└── artifacts/          # Agent-generated plans, logs, summaries
```

---

## License

MIT
