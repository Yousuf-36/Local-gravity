import { session } from 'electron'
import path from 'path'

/**
 * Apply Content-Security-Policy on every renderer response.
 * Rules:
 *   - connect-src hard-coded to 127.0.0.1:8000 (FastAPI only)
 *   - No wildcards anywhere
 *   - unsafe-inline for style-src is required for Tailwind JIT output only
 */
export function applyCSP(): void {
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; " +
            "script-src 'self'; " +
            "style-src 'self' 'unsafe-inline'; " +
            "connect-src 'self' http://127.0.0.1:8000; " +
            "img-src 'self' data: blob:; " +
            "font-src 'self' data:;",
        ],
      },
    })
  })
}

/**
 * Assert that filePath resolves to somewhere inside workspaceRoot.
 * Throws if a path traversal attempt is detected.
 */
export function assertWithinWorkspace(
  filePath: string,
  workspaceRoot: string,
): void {
  if (!workspaceRoot) {
    throw new Error('No workspace open. Open a folder first.')
  }
  const resolved = path.resolve(filePath)
  const root = path.resolve(workspaceRoot)
  // Ensure resolved path starts with root + separator (not just root as prefix)
  const rootWithSep = root.endsWith(path.sep) ? root : root + path.sep
  if (resolved !== root && !resolved.startsWith(rootWithSep)) {
    throw new Error(
      `Path traversal attempt blocked: "${filePath}" escapes workspace root.`,
    )
  }
}
