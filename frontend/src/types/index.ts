// ── Agent Status ──────────────────────────────────────────────────────────────
export type AgentStatus =
  | 'idle'
  | 'running'
  | 'planning'
  | 'executing'
  | 'verifying'
  | 'waiting_approval'
  | 'done'
  | 'error';

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

// ── Typed SSE Frames ──────────────────────────────────────────────────────────
// Every frame from POST /agent/stream matches exactly one of these shapes.
// Discriminant: the `type` field.

export interface PlanFrame {
  type: 'plan';
  task_id: string;
  content: string;
}

export interface ToolCallFrame {
  type: 'tool_call';
  task_id: string;
  call_id: string;
  tool: string;
  args: Record<string, string>;
  destructive: boolean;
}

export interface ToolResultFrame {
  type: 'tool_result';
  task_id: string;
  call_id: string;
  output: string;
  returncode?: number;
  truncated: boolean;
}

export interface FinalAnswerFrame {
  type: 'final_answer';
  task_id: string;
  content: string;
  steps_used: number;
}

export interface ErrorFrame {
  type: 'error';
  task_id: string;
  code:
    | 'ollama_unreachable'
    | 'timeout'
    | 'tool_blocked'
    | 'step_limit'
    | 'agent_error';
  message: string;
}

export interface WaitingApprovalFrame {
  type: 'waiting_approval';
  task_id: string;
  call_id: string;
  tool: string;
  args: Record<string, string>;
  summary: string;
}

export type AgentSSEFrame =
  | PlanFrame
  | ToolCallFrame
  | ToolResultFrame
  | FinalAnswerFrame
  | ErrorFrame
  | WaitingApprovalFrame;

// ── Settings ──────────────────────────────────────────────────────────────────
/** Controls when the HITL approval gate fires. */
export type SafetyLevel = 'strict' | 'balanced' | 'off';

// ── File System ───────────────────────────────────────────────────────────────
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

// ── Terminal ──────────────────────────────────────────────────────────────────
export interface TerminalExecResponse {
  stdout: string;
  stderr: string;
  returncode: number;
}

// ── Ollama ────────────────────────────────────────────────────────────────────
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
