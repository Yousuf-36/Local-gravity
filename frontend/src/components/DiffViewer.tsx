import { useMemo } from 'react';

interface DiffLine {
  type: 'added' | 'removed' | 'unchanged';
  content: string;
  lineNo: number;
}

/**
 * Compute a simple line-level diff between oldText and newText.
 * Uses the longest common subsequence (LCS) approach on lines.
 * Good enough for file patches up to a few hundred lines.
 */
function computeDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split('\n');
  const newLines = newText.split('\n');

  // Build LCS table
  const m = oldLines.length;
  const n = newLines.length;
  const lcs: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      lcs[i][j] =
        oldLines[i - 1] === newLines[j - 1]
          ? lcs[i - 1][j - 1] + 1
          : Math.max(lcs[i - 1][j], lcs[i][j - 1]);
    }
  }

  // Trace back
  const result: DiffLine[] = [];
  let i = m;
  let j = n;
  let lineNo = 1;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      result.unshift({ type: 'unchanged', content: oldLines[i - 1], lineNo: lineNo++ });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || lcs[i][j - 1] >= lcs[i - 1][j])) {
      result.unshift({ type: 'added', content: newLines[j - 1], lineNo: lineNo++ });
      j--;
    } else {
      result.unshift({ type: 'removed', content: oldLines[i - 1], lineNo: lineNo++ });
      i--;
    }
  }
  return result;
}

interface Props {
  /** Original file content (empty string for new files). */
  oldContent: string;
  /** Proposed new content from the write_file tool call. */
  newContent: string;
  /** File path shown in the header. */
  filePath: string;
}

/**
 * DiffViewer — renders a unified diff between old and new file content.
 *
 * Used in the agent panel to show what a write_file call will change before
 * the user approves it. Pure built-in implementation — no external deps.
 */
export function DiffViewer({ oldContent, newContent, filePath }: Props) {
  const lines = useMemo(
    () => computeDiff(oldContent, newContent),
    [oldContent, newContent],
  );

  const addedCount = lines.filter((l) => l.type === 'added').length;
  const removedCount = lines.filter((l) => l.type === 'removed').length;

  return (
    <div className="rounded-lg border border-[var(--border-default)] overflow-hidden text-xs font-mono">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-[var(--bg-elevated)] border-b border-[var(--border-subtle)]">
        <span className="text-[var(--text-secondary)] truncate max-w-[60%]">{filePath}</span>
        <div className="flex items-center gap-3 shrink-0">
          <span style={{ color: 'var(--status-success)' }}>+{addedCount}</span>
          <span style={{ color: 'var(--status-error)' }}>−{removedCount}</span>
        </div>
      </div>

      {/* Diff lines */}
      <div className="overflow-x-auto max-h-64">
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((line, idx) => {
              const bg =
                line.type === 'added'
                  ? 'rgba(0, 200, 80, 0.08)'
                  : line.type === 'removed'
                    ? 'rgba(255, 60, 60, 0.08)'
                    : 'transparent';
              const prefix =
                line.type === 'added' ? '+' : line.type === 'removed' ? '−' : ' ';
              const prefixColor =
                line.type === 'added'
                  ? 'var(--status-success)'
                  : line.type === 'removed'
                    ? 'var(--status-error)'
                    : 'var(--text-muted)';

              return (
                <tr key={idx} style={{ background: bg }}>
                  <td
                    className="select-none w-8 text-right pr-2 pl-1 text-[var(--text-muted)] border-r border-[var(--border-subtle)]"
                    style={{ opacity: 0.5 }}
                  >
                    {line.lineNo}
                  </td>
                  <td
                    className="w-4 text-center select-none"
                    style={{ color: prefixColor }}
                  >
                    {prefix}
                  </td>
                  <td className="pl-2 pr-4 py-px text-[var(--text-primary)] whitespace-pre">
                    {line.content}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
