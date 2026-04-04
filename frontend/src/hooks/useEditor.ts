import { useState, useCallback } from 'react';
import { useAppStore } from '../store';
import { filesApi } from '../api/files';

export function useEditor() {
  const { openTabs, activeTab, openTab, closeTab, setActiveTab } = useAppStore();
  const [fileContents, setFileContents] = useState<Record<string, string>>({});
  const [loadingFiles, setLoadingFiles] = useState<Record<string, boolean>>({});
  const [errorFiles, setErrorFiles] = useState<Record<string, string | null>>({});

  const loadFile = useCallback(async (path: string) => {
    if (fileContents[path] !== undefined || loadingFiles[path]) return; // already loaded or loading

    setLoadingFiles(prev => ({ ...prev, [path]: true }));
    setErrorFiles(prev => ({ ...prev, [path]: null }));

    try {
      const content = await filesApi.readFile(path);
      setFileContents(prev => ({ ...prev, [path]: content }));
    } catch (err) {
      setErrorFiles(prev => ({ 
        ...prev, 
        [path]: err instanceof Error ? err.message : 'Failed to read file' 
      }));
    } finally {
      setLoadingFiles(prev => ({ ...prev, [path]: false }));
    }
  }, [fileContents, loadingFiles]);

  const handleOpenFile = useCallback((path: string) => {
    openTab(path);
    if (fileContents[path] === undefined) {
      loadFile(path).catch(() => {
        // error is already captured in errorFiles state by loadFile
      });
    }
  }, [openTab, fileContents, loadFile]);

  const handleCloseFile = useCallback((path: string) => {
    closeTab(path);
  }, [closeTab]);

  return {
    openTabs,
    activeTab,
    setActiveTab,
    openFile: handleOpenFile,
    closeFile: handleCloseFile,
    fileContents,
    loadingFiles,
    errorFiles
  };
}
