// --- Agent Types ---
export type AgentStatus = 'idle' | 'planning' | 'executing' | 'verifying' | 'waiting_approval' | 'done' | 'error';

export interface AgentTask {
  id: string;
  created_at: string;
  status: AgentStatus;
  description: string;
  model: string;
  workspace: string;
  artifacts: string[];
  log_path: string;
  error?: string;
}

// --- File System Types ---
export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: FileNode[];
}

export interface FileReadResponse {
  path: string;
  content: string;
  size: number;
  language: string;
}

// --- Terminal Types ---
export interface TerminalExecResponse {
  stdout: string;
  stderr: string;
  returncode: number;
}

// --- Ollama Types ---
export interface OllamaModel {
  name: string;
  size?: number;
  modified_at?: string;
}

export interface OllamaStatusResponse {
  ok: boolean;
  models: string[];
  active_model: string;
  error?: string;
}
