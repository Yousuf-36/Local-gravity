import { Component, ErrorInfo, ReactNode } from 'react';
import { UI_STRINGS } from '../constants';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // errors are captured in state; intentionally not logged to avoid console output
    void error;
    void errorInfo;
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center h-full w-full bg-[var(--bg-base)] text-[var(--text-primary)] p-6">
          <div className="bg-[var(--bg-elevated)] border border-[var(--status-error)] rounded p-4 max-w-lg w-full">
            <h2 className="text-[var(--status-error)] font-bold mb-2">Something went wrong.</h2>
            <pre className="text-xs font-mono text-[var(--text-secondary)] whitespace-pre-wrap mb-4 overflow-auto max-h-40">
              {this.state.error?.message || 'Unknown error'}
            </pre>
            <button
              onClick={this.handleReset}
              className="bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)] border border-[var(--border-default)] px-3 py-1.5 rounded text-sm transition-colors w-full"
            >
              {UI_STRINGS.RETRY_BUTTON}
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
