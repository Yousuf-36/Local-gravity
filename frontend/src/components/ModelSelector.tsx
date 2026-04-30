import { useEffect } from 'react';
import { useAppStore } from '../store';

function formatSize(bytes?: number): string {
  if (!bytes) return '';
  const gb = bytes / 1024 ** 3;
  return gb >= 1 ? ` (${gb.toFixed(1)} GB)` : ` (${(bytes / 1024 ** 2).toFixed(0)} MB)`;
}

/**
 * ModelSelector — fetches available Ollama models on mount and renders a
 * styled <select> bound to Zustand's selectedModel / setSelectedModel.
 *
 * Persisted: the selected model survives page reload via Zustand persist middleware.
 */
export function ModelSelector() {
  const { availableModels, setAvailableModels, selectedModel, setSelectedModel } = useAppStore();

  useEffect(() => {
    window.api
      .listModels()
      .then(setAvailableModels)
      .catch(() => {
        /* Ollama offline — keep existing list */
      });
  }, [setAvailableModels]);

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const model = e.target.value;
    setSelectedModel(model);
    try {
      await window.api.switchModel(model);
    } catch {
      /* switch failure is non-fatal — next stream call re-validates */
    }
  };

  if (availableModels.length === 0) {
    return (
      <span className="text-[10px] font-mono text-[var(--text-muted)] px-2 py-0.5 rounded border border-[var(--border-subtle)] bg-[var(--bg-elevated)]">
        {selectedModel || 'no models'}
      </span>
    );
  }

  return (
    <select
      value={selectedModel}
      onChange={handleChange}
      className="model-select"
      aria-label="Select Ollama model"
    >
      {availableModels.map((m) => (
        <option key={m.name} value={m.name}>
          {m.name}{formatSize(m.size)}
        </option>
      ))}
    </select>
  );
}
