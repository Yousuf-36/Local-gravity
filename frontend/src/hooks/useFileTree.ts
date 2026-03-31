import { useCallback } from 'react';
import { useAppStore } from '../store';
import { filesApi } from '../api/files';

export function useFileTree() {
  const { 
    workspacePath, setWorkspacePath, 
    fileTree, setFileTree, 
    isFileTreeLoading, setIsFileTreeLoading, 
    fileTreeError, setFileTreeError 
  } = useAppStore();

  const fetchTree = useCallback(async (path: string) => {
    setIsFileTreeLoading(true);
    setFileTreeError(null);
    try {
      const tree = await filesApi.getTree(path);
      setFileTree(tree);
    } catch (err) {
      setFileTreeError(err instanceof Error ? err.message : 'Unknown error fetching file tree');
      setFileTree(null);
    } finally {
      setIsFileTreeLoading(false);
    }
  }, [setFileTree, setFileTreeError, setIsFileTreeLoading]);

  const openWorkspace = useCallback(async () => {
    try {
      const path = await filesApi.openFolder();
      if (path) {
        setWorkspacePath(path);
        await fetchTree(path);
      }
    } catch (err) {
      setFileTreeError(err instanceof Error ? err.message : 'Failed to open workspace');
    }
  }, [fetchTree, setFileTreeError, setWorkspacePath]);

  const refreshTree = useCallback(async () => {
    if (workspacePath) {
      await fetchTree(workspacePath);
    }
  }, [fetchTree, workspacePath]);

  return {
    workspacePath,
    fileTree,
    isLoading: isFileTreeLoading,
    error: fileTreeError,
    openWorkspace,
    refreshTree
  };
}
