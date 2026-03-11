/**
 * Python subprocess bridge.
 *
 * Manages a long-running Python process that communicates via JSON-RPC
 * over stdin/stdout. The bridge lazily spawns the process on first call
 * and keeps it alive for subsequent requests.
 */

import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs';
import { BridgeRequest, BridgeResponse } from './types';

const BRIDGE_SCRIPT = path.join(__dirname, '..', 'scripts', 'bridge.py');

/** Find the Python executable inside the package's venv. */
function findPython(): string {
  const pkgRoot = path.join(__dirname, '..');
  const venvPython = path.join(pkgRoot, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  // Fallback: try system python
  for (const cmd of ['python3', 'python']) {
    try {
      const { execSync } = require('child_process');
      execSync(`${cmd} --version`, { stdio: 'ignore' });
      return cmd;
    } catch {
      continue;
    }
  }
  throw new Error(
    'Python 3.9+ not found. Run the postinstall script or install Python manually.'
  );
}

export class PythonBridge extends EventEmitter {
  private process: ChildProcess | null = null;
  private pythonPath: string;
  private requestId = 0;
  private pending = new Map<number, {
    resolve: (value: unknown) => void;
    reject: (reason: Error) => void;
  }>();
  private buffer = '';
  private ready = false;
  private readyPromise: Promise<void> | null = null;

  constructor() {
    super();
    this.pythonPath = findPython();
  }

  /** Start the Python bridge process. */
  private start(): Promise<void> {
    if (this.readyPromise) return this.readyPromise;

    this.readyPromise = new Promise<void>((resolve, reject) => {
      this.process = spawn(this.pythonPath, [BRIDGE_SCRIPT], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          PYTHONDONTWRITEBYTECODE: '1',
        },
      });

      this.process.stdout!.on('data', (data: Buffer) => {
        this.buffer += data.toString();
        let newlineIdx: number;
        while ((newlineIdx = this.buffer.indexOf('\n')) !== -1) {
          const line = this.buffer.slice(0, newlineIdx).trim();
          this.buffer = this.buffer.slice(newlineIdx + 1);
          if (!line) continue;
          this.handleLine(line);
        }
      });

      this.process.stderr!.on('data', (data: Buffer) => {
        const msg = data.toString().trim();
        if (msg) {
          this.emit('log', msg);
        }
      });

      this.process.on('error', (err) => {
        if (!this.ready) {
          reject(err);
        }
        this.emit('error', err);
      });

      this.process.on('close', (code) => {
        this.ready = false;
        this.readyPromise = null;
        this.process = null;

        // Reject all pending requests
        for (const [, { reject: rej }] of this.pending) {
          rej(new Error(`Python bridge exited with code ${code}`));
        }
        this.pending.clear();
        this.emit('close', code);
      });

      // Wait for ready signal
      const onLine = (line: string) => {
        try {
          const msg = JSON.parse(line);
          if (msg.type === 'ready') {
            this.ready = true;
            resolve();
          }
        } catch {
          // Not JSON yet, ignore
        }
      };

      // Temporary handler for the ready message
      const origHandle = this.handleLine.bind(this);
      this.handleLine = (line: string) => {
        onLine(line);
        if (this.ready) {
          this.handleLine = origHandle;
        }
        origHandle(line);
      };

      // Timeout for startup
      setTimeout(() => {
        if (!this.ready) {
          reject(new Error('Python bridge startup timed out (30s)'));
          this.kill();
        }
      }, 30000);
    });

    return this.readyPromise;
  }

  private handleLine(line: string): void {
    try {
      const response: BridgeResponse = JSON.parse(line);
      if (response.id !== undefined && this.pending.has(response.id)) {
        const { resolve, reject } = this.pending.get(response.id)!;
        this.pending.delete(response.id);
        if (response.error) {
          reject(new Error(response.error.message));
        } else {
          resolve(response.result);
        }
      }
    } catch {
      // Not a valid response, ignore
    }
  }

  /** Send a request to the Python bridge and wait for the response. */
  async call(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    await this.start();

    const id = ++this.requestId;
    const request: BridgeRequest = { id, method, params };

    return new Promise<unknown>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });

      const line = JSON.stringify(request) + '\n';
      if (!this.process?.stdin?.writable) {
        this.pending.delete(id);
        reject(new Error('Python bridge stdin not writable'));
        return;
      }

      this.process.stdin.write(line, (err) => {
        if (err) {
          this.pending.delete(id);
          reject(err);
        }
      });
    });
  }

  /** Check if the bridge is running. */
  isAlive(): boolean {
    return this.ready && this.process !== null;
  }

  /** Kill the bridge process. */
  kill(): void {
    if (this.process) {
      this.process.kill('SIGTERM');
      this.process = null;
      this.ready = false;
      this.readyPromise = null;
    }
  }

  /** Gracefully shut down the bridge. */
  async shutdown(): Promise<void> {
    if (!this.isAlive()) return;
    try {
      await this.call('shutdown', {});
    } catch {
      // Ignore errors during shutdown
    }
    this.kill();
  }
}

// Singleton bridge instance
let _bridge: PythonBridge | null = null;

/** Get or create the singleton bridge instance. */
export function getBridge(): PythonBridge {
  if (!_bridge) {
    _bridge = new PythonBridge();
  }
  return _bridge;
}

/** Shut down the singleton bridge. */
export async function shutdownBridge(): Promise<void> {
  if (_bridge) {
    await _bridge.shutdown();
    _bridge = null;
  }
}
