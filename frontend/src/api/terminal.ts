export const terminalApi = {
  /**
   * Execute a sandboxed terminal command
   */
  execCommand: async (cmd: string): Promise<unknown> => {
    return window.api.execCommand(cmd);
  },

  /**
   * Listen to terminal output stream
   */
  onOutput: (callback: (line: string) => void): (() => void) => {
    return window.api.onTerminalOutput(callback);
  },
};
