/**
 * TypeScript type definitions for transcribe-cli.
 */

/** Supported Whisper model sizes. */
export type ModelSize = 'tiny' | 'base' | 'small' | 'medium' | 'large-v3';

/** Supported output formats. */
export type OutputFormat = 'txt' | 'srt' | 'vtt' | 'json';

/** Compute device selection. */
export type Device = 'auto' | 'cpu' | 'cuda';

/** Compute precision type. */
export type ComputeType = 'auto' | 'int8' | 'float16' | 'float32';

/** A single word with timing information. */
export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

/** A transcription segment with timing and optional speaker. */
export interface TranscriptionSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  speaker?: string;
  words?: WordTimestamp[];
}

/** Result of a transcription operation. */
export interface TranscriptionResult {
  inputFile: string;
  text: string;
  language: string;
  duration: number | null;
  wordCount: number;
  speakers: string[];
  segments: TranscriptionSegment[];
}

/** Options for file transcription. */
export interface TranscribeOptions {
  /** Whisper model size. Default: 'base' */
  model?: ModelSize;
  /** Language code or 'auto'. Default: 'auto' */
  language?: string;
  /** Output format. Default: 'json' */
  format?: OutputFormat;
  /** Output directory. Default: same as input */
  outputDir?: string;
  /** Enable speaker diarization. Default: false */
  diarize?: boolean;
  /** Enable word-level timestamps. Default: false */
  wordTimestamps?: boolean;
  /** Compute device. Default: 'auto' */
  device?: Device;
  /** Compute precision. Default: 'auto' */
  computeType?: ComputeType;
}

/** Options for batch transcription. */
export interface BatchOptions extends TranscribeOptions {
  /** Max concurrent transcriptions. Default: 5 */
  concurrency?: number;
  /** Scan subdirectories. Default: false */
  recursive?: boolean;
}

/** Result of a batch transcription. */
export interface BatchResult {
  totalFiles: number;
  successful: number;
  failed: number;
  results: Array<{
    inputFile: string;
    outputFile: string | null;
    success: boolean;
    error: string | null;
  }>;
}

/** Options for live audio transcription. */
export interface LiveTranscribeOptions {
  /** Whisper model size. Default: 'base' */
  model?: ModelSize;
  /** Language code or 'auto'. Default: 'auto' */
  language?: string;
  /** Audio sample rate in Hz. Default: 16000 */
  sampleRate?: number;
  /** Number of audio channels. Default: 1 (mono) */
  channels?: number;
  /** Sample width in bytes. Default: 2 (16-bit) */
  sampleWidth?: number;
  /** Buffer duration in seconds before transcribing. Default: 5 */
  chunkDuration?: number;
  /** Enable speaker diarization. Default: false */
  diarize?: boolean;
  /** Enable word-level timestamps. Default: false */
  wordTimestamps?: boolean;
  /** Compute device. Default: 'auto' */
  device?: Device;
  /** Compute precision. Default: 'auto' */
  computeType?: ComputeType;
}

/** A live transcription event. */
export interface LiveTranscriptEvent {
  type: 'transcript';
  text: string;
  segments: TranscriptionSegment[];
  isFinal: boolean;
  timestamp: number;
}

/** Bridge request message. */
export interface BridgeRequest {
  id: number;
  method: string;
  params: Record<string, unknown>;
}

/** Bridge response message. */
export interface BridgeResponse {
  id: number;
  result?: unknown;
  error?: { message: string; code?: string };
}
