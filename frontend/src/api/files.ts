import { FileNode } from '../types';

export const filesApi = {
  /**
   * Open the native OS folder picker
   */
  openFolder: async (): Promise<string | null> => {
    return window.api.openFolder();
  },

  /**
   * Read the contents of a file
   */
  readFile: async (filePath: string): Promise<string> => {
    return window.api.readFile(filePath);
  },

  /**
   * Write contents to a file
   */
  writeFile: async (filePath: string, content: string): Promise<{ ok: boolean }> => {
    return window.api.writeFile(filePath, content);
  },

  /**
   * Get the directory tree structure by fetching from the backend
   */
  getTree: async (workspacePath: string): Promise<FileNode> => {
    const res = await fetch(`http://127.0.0.1:8000/files/tree?workspace=${encodeURIComponent(workspacePath)}`);
    if (!res.ok) {
      throw new Error('Failed to fetch file tree');
    }
    return res.json() as Promise<FileNode>;
  },
};
