/**
 * setup.ts — Global test setup for vitest + @testing-library/react
 *
 * Imports jest-dom matchers so toBeInTheDocument(), toHaveTextContent(), etc.
 * are available in all test files without explicit import.
 *
 * Also mocks window.api (the Electron IPC bridge) so component tests that
 * call window.api.approveToolCall / window.api.denyToolCall don't throw.
 */
import '@testing-library/jest-dom';
import { vi } from 'vitest';

// ── Mock the Electron IPC bridge ──────────────────────────────────────────────
// Components import window.api; we stub it here so tests never hit Electron.
Object.defineProperty(window, 'api', {
  value: {
    sendAgentMessage: vi.fn().mockResolvedValue(undefined),
    onAgentStream: vi.fn().mockReturnValue(vi.fn()),
    approveToolCall: vi.fn().mockResolvedValue(undefined),
    denyToolCall: vi.fn().mockResolvedValue(undefined),
    openFolder: vi.fn().mockResolvedValue('/test/workspace'),
    getSettings: vi.fn().mockResolvedValue({}),
    saveSettings: vi.fn().mockResolvedValue(undefined),
    readFile: vi.fn().mockResolvedValue({ content: '', language: 'plaintext' }),
    writeFile: vi.fn().mockResolvedValue({ ok: true }),
    listFiles: vi.fn().mockResolvedValue({ name: 'root', type: 'directory', children: [] }),
  },
  writable: true,
});
