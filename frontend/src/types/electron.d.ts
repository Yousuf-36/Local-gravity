export interface ElectronAPI {
  sendAgentMessage: (msg: string) => Promise<{ done: boolean }>;
  onAgentStream: (cb: (chunk: string) => void) => () => void;
  openFolder: () => Promise<string | null>;
  readFile: (filePath: string) => Promise<string>;
  writeFile: (filePath: string, content: string) => Promise<{ ok: boolean }>;
  execCommand: (cmd: string) => Promise<unknown>;
  onTerminalOutput: (cb: (line: string) => void) => () => void;
  listModels: () => Promise<string[]>;
  switchModel: (model: string) => Promise<unknown>;
}

declare global {
  interface Window {
    api: ElectronAPI;
  }
}
