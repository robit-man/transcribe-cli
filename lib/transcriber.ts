/**
 * File transcription API.
 *
 * Provides async functions for transcribing audio/video files and
 * batch processing directories. Delegates to the Python backend
 * via the bridge.
 */

import { getBridge } from './bridge';
import {
  TranscribeOptions,
  TranscriptionResult,
  BatchOptions,
  BatchResult,
} from './types';

/**
 * Transcribe a single audio or video file.
 *
 * @example
 * ```ts
 * import { transcribe } from 'transcribe-cli';
 *
 * const result = await transcribe('meeting.mp3', {
 *   model: 'base',
 *   diarize: true,
 *   wordTimestamps: true,
 * });
 * console.log(result.text);
 * console.log(result.speakers);
 * ```
 */
export async function transcribe(
  file: string,
  options: TranscribeOptions = {}
): Promise<TranscriptionResult> {
  const bridge = getBridge();
  const result = await bridge.call('transcribe', {
    file,
    model: options.model ?? 'base',
    language: options.language ?? 'auto',
    format: options.format ?? 'json',
    output_dir: options.outputDir ?? null,
    diarize: options.diarize ?? false,
    word_timestamps: options.wordTimestamps ?? false,
    device: options.device ?? 'auto',
    compute_type: options.computeType ?? 'auto',
  });
  return result as TranscriptionResult;
}

/**
 * Batch transcribe all audio/video files in a directory.
 *
 * @example
 * ```ts
 * import { transcribeBatch } from 'transcribe-cli';
 *
 * const result = await transcribeBatch('./recordings', {
 *   recursive: true,
 *   concurrency: 3,
 *   format: 'srt',
 *   diarize: true,
 * });
 * console.log(`${result.successful}/${result.totalFiles} succeeded`);
 * ```
 */
export async function transcribeBatch(
  directory: string,
  options: BatchOptions = {}
): Promise<BatchResult> {
  const bridge = getBridge();
  const result = await bridge.call('batch', {
    directory,
    model: options.model ?? 'base',
    language: options.language ?? 'auto',
    format: options.format ?? 'json',
    output_dir: options.outputDir ?? null,
    concurrency: options.concurrency ?? 5,
    recursive: options.recursive ?? false,
    diarize: options.diarize ?? false,
    word_timestamps: options.wordTimestamps ?? false,
    device: options.device ?? 'auto',
    compute_type: options.computeType ?? 'auto',
  });
  return result as BatchResult;
}

/**
 * Get information about the transcription environment.
 *
 * @returns Object with version, available models, and dependency status.
 */
export async function getInfo(): Promise<{
  version: string;
  python: string;
  fasterWhisper: boolean;
  ffmpeg: boolean;
  pyannote: boolean;
}> {
  const bridge = getBridge();
  const result = await bridge.call('info', {});
  return result as {
    version: string;
    python: string;
    fasterWhisper: boolean;
    ffmpeg: boolean;
    pyannote: boolean;
  };
}
