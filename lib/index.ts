/**
 * transcribe-cli — Local audio/video transcription with speaker diarization.
 *
 * @example
 * ```ts
 * import { transcribe, TranscribeLive } from 'transcribe-cli';
 *
 * // File transcription
 * const result = await transcribe('meeting.mp3', { diarize: true });
 * console.log(result.text);
 *
 * // Live audio
 * const live = new TranscribeLive({ model: 'base' });
 * live.on('transcript', (evt) => console.log(evt.text));
 * live.write(pcmBuffer);
 * await live.finish();
 * ```
 *
 * @packageDocumentation
 */

// Core API
export { transcribe, transcribeBatch, getInfo } from './transcriber';

// Live audio
export { TranscribeLive } from './live';

// Bridge management
export { getBridge, shutdownBridge, PythonBridge } from './bridge';

// Types
export type {
  ModelSize,
  OutputFormat,
  Device,
  ComputeType,
  WordTimestamp,
  TranscriptionSegment,
  TranscriptionResult,
  TranscribeOptions,
  BatchOptions,
  BatchResult,
  LiveTranscribeOptions,
  LiveTranscriptEvent,
} from './types';
