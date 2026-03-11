#!/usr/bin/env node
/**
 * CLI wrapper for transcribe-cli.
 *
 * Delegates to the Python CLI for full command support, or uses the
 * Node.js API directly for key operations.
 */

import { spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

const pkgRoot = path.join(__dirname, '..', '..');
const venvPython = path.join(pkgRoot, '.venv', 'bin', 'python');
const venvTranscribe = path.join(pkgRoot, '.venv', 'bin', 'transcribe');

function findExecutable(): { cmd: string; args: string[] } {
  // Prefer the venv's transcribe command
  if (fs.existsSync(venvTranscribe)) {
    return { cmd: venvTranscribe, args: [] };
  }
  // Fallback: run via python -m
  if (fs.existsSync(venvPython)) {
    return { cmd: venvPython, args: ['-m', 'transcribe_cli.cli.main'] };
  }
  // Last resort: system python
  return { cmd: 'python3', args: ['-m', 'transcribe_cli.cli.main'] };
}

const args = process.argv.slice(2);

// Special handling for --version
if (args.includes('--version') || args.includes('-v')) {
  try {
    const pkg = JSON.parse(
      fs.readFileSync(path.join(pkgRoot, 'package.json'), 'utf-8')
    );
    console.log(`transcribe-cli v${pkg.version} (npm)`);
  } catch {
    console.log('transcribe-cli (version unknown)');
  }
  process.exit(0);
}

const { cmd, args: baseArgs } = findExecutable();

const child = spawn(cmd, [...baseArgs, ...args], {
  stdio: 'inherit',
  env: {
    ...process.env,
    // Ensure the venv's site-packages are used
    VIRTUAL_ENV: path.join(pkgRoot, '.venv'),
    PATH: `${path.join(pkgRoot, '.venv', 'bin')}:${process.env.PATH}`,
  },
});

child.on('close', (code) => {
  process.exit(code ?? 1);
});

child.on('error', (err) => {
  if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
    console.error(
      'Error: Python environment not found. Run: npm rebuild transcribe-cli'
    );
  } else {
    console.error(`Error: ${err.message}`);
  }
  process.exit(1);
});
