/**
 * Live audio transcription API.
 *
 * Provides a Writable stream interface for real-time audio transcription.
 * Feed raw PCM audio data and receive transcript events as they're produced.
 */

import { Writable, WritableOptions } from 'stream';
import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs';
import {
  LiveTranscribeOptions,
  LiveTranscriptEvent,
  TranscriptionSegment,
} from './types';

const LIVE_WORKER = path.join(__dirname, '..', 'scripts', 'live_worker.py');

function findPython(): string {
  const pkgRoot = path.join(__dirname, '..');
  const venvPython = path.join(pkgRoot, '.venv', 'bin', 'python');
  if (fs.existsSync(venvPython)) return venvPython;
  for (const cmd of ['python3', 'python']) {
    try {
      const { execSync } = require('child_process');
      execSync(`${cmd} --version`, { stdio: 'ignore' });
      return cmd;
    } catch { continue; }
  }
  throw new Error('Python 3.9+ not found.');
}

export interface TranscribeLive {
  on(event: 'transcript', listener: (evt: LiveTranscriptEvent) => void): this;
  on(event: 'ready', listener: () => void): this;
  on(event: 'error', listener: (err: Error) => void): this;
  on(event: 'close', listener: () => void): this;
  on(event: string, listener: (...args: unknown[]) => void): this;
}

/**
 * Live audio transcription stream.
 *
 * @example
 * ```ts
 * import { TranscribeLive } from 'transcribe-cli';
 *
 * const live = new TranscribeLive({ model: 'base', sampleRate: 16000 });
 *
 * live.on('ready', () => console.log('Model loaded, ready for audio'));
 *
 * live.on('transcript', (evt) => {
 *   console.log(`[${evt.isFinal ? 'FINAL' : 'partial'}] ${evt.text}`);
 * });
 *
 * // Pipe PCM audio from any source
 * microphoneStream.pipe(live);
 *
 * // Or write buffers directly
 * live.write(pcmBuffer);
 *
 * // Finish and get any remaining audio transcribed
 * await live.finish();
 * ```
 */
export class TranscribeLive extends EventEmitter {
  private process: ChildProcess | null = null;
  private pythonPath: string;
  private options: Required<LiveTranscribeOptions>;
  private buffer = '';
  private _ready = false;
  private _finished = false;
  private writable: Writable;

  constructor(options: LiveTranscribeOptions = {}) {
    super();
    this.pythonPath = findPython();
    this.options = {
      model: options.model ?? 'base',
      language: options.language ?? 'auto',
      sampleRate: options.sampleRate ?? 16000,
      channels: options.channels ?? 1,
      sampleWidth: options.sampleWidth ?? 2,
      chunkDuration: options.chunkDuration ?? 5,
      diarize: options.diarize ?? false,
      wordTimestamps: options.wordTimestamps ?? false,
      device: options.device ?? 'auto',
      computeType: options.computeType ?? 'auto',
    };

    this.writable = new Writable({
      write: (chunk: Buffer, _encoding: string, callback: (error?: Error | null) => void) => {
        if (this.process?.stdin?.writable) {
          this.process.stdin.write(chunk, callback);
        } else {
          callback(new Error('Live transcription process not running'));
        }
      },
      final: (callback: (error?: Error | null) => void) => {
        this.finishInternal().then(() => callback()).catch(callback);
      },
    });

    this.spawn();
  }

  /** Get the writable stream for piping audio data. */
  get stream(): Writable {
    return this.writable;
  }

  /** Whether the model is loaded and ready for audio. */
  get ready(): boolean {
    return this._ready;
  }

  /** Write raw PCM audio data. */
  write(chunk: Buffer): boolean {
    return this.writable.write(chunk);
  }

  /** Pipe a readable stream into this live transcriber. */
  pipe(source: NodeJS.ReadableStream): this {
    source.pipe(this.writable);
    return this;
  }

  private spawn(): void {
    this.process = spawn(this.pythonPath, [LIVE_WORKER], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONDONTWRITEBYTECODE: '1',
      },
    });

    // Send config as first line
    const config = JSON.stringify({
      model: this.options.model,
      language: this.options.language,
      sample_rate: this.options.sampleRate,
      channels: this.options.channels,
      sample_width: this.options.sampleWidth,
      chunk_duration: this.options.chunkDuration,
      diarize: this.options.diarize,
      word_timestamps: this.options.wordTimestamps,
      device: this.options.device,
      compute_type: this.options.computeType,
    }) + '\n';

    this.process.stdin!.write(config);

    this.process.stdout!.on('data', (data: Buffer) => {
      this.buffer += data.toString();
      let idx: number;
      while ((idx = this.buffer.indexOf('\n')) !== -1) {
        const line = this.buffer.slice(0, idx).trim();
        this.buffer = this.buffer.slice(idx + 1);
        if (line) this.handleLine(line);
      }
    });

    this.process.stderr!.on('data', (data: Buffer) => {
      const msg = data.toString().trim();
      if (msg && !msg.startsWith('Downloading') && !msg.startsWith('Loading')) {
        this.emit('error', new Error(msg));
      }
    });

    this.process.on('close', () => {
      this.process = null;
      this._ready = false;
      this.emit('close');
    });

    this.process.on('error', (err) => {
      this.emit('error', err);
    });
  }

  private handleLine(line: string): void {
    try {
      const msg = JSON.parse(line);
      if (msg.type === 'ready') {
        this._ready = true;
        this.emit('ready');
      } else if (msg.type === 'transcript') {
        const event: LiveTranscriptEvent = {
          type: 'transcript',
          text: msg.text ?? '',
          segments: msg.segments ?? [],
          isFinal: msg.is_final ?? true,
          timestamp: msg.timestamp ?? Date.now() / 1000,
        };
        this.emit('transcript', event);
      } else if (msg.type === 'error') {
        this.emit('error', new Error(msg.message));
      }
    } catch {
      // Not valid JSON, ignore
    }
  }

  /** Signal end of audio and wait for final transcription. */
  async finish(): Promise<void> {
    return this.finishInternal();
  }

  private finishInternal(): Promise<void> {
    if (this._finished) return Promise.resolve();
    this._finished = true;

    return new Promise<void>((resolve) => {
      if (!this.process) {
        resolve();
        return;
      }

      this.process.on('close', () => resolve());

      // Close stdin to signal EOF
      if (this.process.stdin?.writable) {
        this.process.stdin.end();
      }

      // Force kill after 30s
      setTimeout(() => {
        if (this.process) {
          this.process.kill('SIGKILL');
          resolve();
        }
      }, 30000);
    });
  }

  /** Force stop the live transcription. */
  stop(): void {
    this._finished = true;
    if (this.process) {
      this.process.kill('SIGTERM');
      this.process = null;
    }
  }
}
