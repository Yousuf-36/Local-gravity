/**
 * StatusBadge.test.tsx — Tests for components/StatusBadge.tsx
 *
 * Coverage:
 *   idle   — shows correct label, no animated dot
 *   running — shows animated dot
 *   error  — shows correct color (error label)
 *   done   — no animated dot
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '../../components/StatusBadge';

describe('StatusBadge', () => {
  it('renders with status idle — shows correct label', () => {
    render(<StatusBadge status="idle" />);
    expect(screen.getByText('idle')).toBeInTheDocument();
  });

  it('renders with status idle — no animated dot', () => {
    const { container } = render(<StatusBadge status="idle" />);
    // dot has class animate-pulse; none should be present for idle
    const dot = container.querySelector('.animate-pulse');
    expect(dot).toBeNull();
  });

  it('renders with status running — shows animated dot', () => {
    const { container } = render(<StatusBadge status="running" />);
    const dot = container.querySelector('.animate-pulse');
    expect(dot).not.toBeNull();
  });

  it('renders with status running — shows "running" label', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByText('running')).toBeInTheDocument();
  });

  it('renders with status error — shows "error" label', () => {
    render(<StatusBadge status="error" />);
    expect(screen.getByText('error')).toBeInTheDocument();
  });

  it('renders with status error — no animated dot', () => {
    const { container } = render(<StatusBadge status="error" />);
    const dot = container.querySelector('.animate-pulse');
    expect(dot).toBeNull();
  });

  it('renders with status done — shows "done" label', () => {
    render(<StatusBadge status="done" />);
    expect(screen.getByText('done')).toBeInTheDocument();
  });

  it('renders with status done — no animated dot', () => {
    const { container } = render(<StatusBadge status="done" />);
    const dot = container.querySelector('.animate-pulse');
    expect(dot).toBeNull();
  });
});
