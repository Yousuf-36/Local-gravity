/**
 * ApprovalCard.test.tsx — Tests for components/ApprovalCard.tsx
 *
 * Coverage:
 *   Renders tool name and args
 *   Approve button calls window.api.approveToolCall
 *   Deny button calls window.api.denyToolCall
 *   Summary text is visible
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ApprovalCard } from '../../components/ApprovalCard';
import type { WaitingApprovalFrame } from '../../types';

// ── Mock zustand store ────────────────────────────────────────────────────────
// ApprovalCard calls useAppStore().setPendingApproval — we mock the module so
// tests don't need a real store.
const mockSetPendingApproval = vi.fn();
vi.mock('../../store', () => ({
  useAppStore: () => ({
    setPendingApproval: mockSetPendingApproval,
  }),
}));

const MOCK_FRAME: WaitingApprovalFrame = {
  type: 'waiting_approval',
  task_id: 'task-abc',
  call_id: 'call-xyz',
  tool: 'write_file',
  args: { path: 'src/index.ts', content: 'console.log("hello");' },
  summary: 'Write 21 bytes to src/index.ts',
};

describe('ApprovalCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the tool name', () => {
    render(<ApprovalCard frame={MOCK_FRAME} />);
    expect(screen.getByText('write_file')).toBeInTheDocument();
  });

  it('renders summary text', () => {
    render(<ApprovalCard frame={MOCK_FRAME} />);
    expect(screen.getByText('Write 21 bytes to src/index.ts')).toBeInTheDocument();
  });

  it('renders path arg (non-content keys shown as args)', () => {
    render(<ApprovalCard frame={MOCK_FRAME} />);
    // The path arg key should appear
    expect(screen.getByText('path:')).toBeInTheDocument();
    expect(screen.getByText('src/index.ts')).toBeInTheDocument();
  });

  it('renders Approve button', () => {
    render(<ApprovalCard frame={MOCK_FRAME} />);
    expect(screen.getByText('Approve')).toBeInTheDocument();
  });

  it('renders Deny button', () => {
    render(<ApprovalCard frame={MOCK_FRAME} />);
    expect(screen.getByText('Deny')).toBeInTheDocument();
  });

  it('Approve button calls window.api.approveToolCall', async () => {
    render(<ApprovalCard frame={MOCK_FRAME} />);
    fireEvent.click(screen.getByText('Approve'));
    await waitFor(() => {
      expect(window.api.approveToolCall).toHaveBeenCalledWith('task-abc', 'call-xyz');
    });
  });

  it('Deny button calls window.api.denyToolCall', async () => {
    render(<ApprovalCard frame={MOCK_FRAME} />);
    fireEvent.click(screen.getByText('Deny'));
    await waitFor(() => {
      expect(window.api.denyToolCall).toHaveBeenCalledWith('task-abc', 'call-xyz');
    });
  });

  it('calls setPendingApproval(null) after approve', async () => {
    render(<ApprovalCard frame={MOCK_FRAME} />);
    fireEvent.click(screen.getByText('Approve'));
    await waitFor(() => {
      expect(mockSetPendingApproval).toHaveBeenCalledWith(null);
    });
  });
});
