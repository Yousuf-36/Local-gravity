import { ErrorBoundary } from './components/ErrorBoundary';
import { AppShell } from './components/AppShell';

function App() {
  return (
    <ErrorBoundary>
      <AppShell />
    </ErrorBoundary>
  );
}

export default App;
