#!/usr/bin/env node
/**
 * postinstall script for transcribe-cli npm package.
 *
 * Automatically sets up the Python environment:
 * 1. Finds Python 3.9+
 * 2. Creates a virtual environment
 * 3. Installs the Python package with faster-whisper
 * 4. Pre-downloads the default Whisper model (base)
 *
 * Runs silently — only errors produce output.
 */

const { execSync, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const PKG_ROOT = path.resolve(__dirname, '..');
const VENV_DIR = path.join(PKG_ROOT, '.venv');
const VENV_PYTHON = path.join(VENV_DIR, 'bin', 'python');
const VENV_PIP = path.join(VENV_DIR, 'bin', 'pip');
const DEFAULT_MODEL = process.env.TRANSCRIBE_MODEL || 'base';

// Quiet mode — suppress output unless TRANSCRIBE_VERBOSE is set
const VERBOSE = process.env.TRANSCRIBE_VERBOSE === '1';

function log(msg) {
  if (VERBOSE) {
    console.log(`[transcribe-cli] ${msg}`);
  }
}

function warn(msg) {
  console.warn(`[transcribe-cli] WARN: ${msg}`);
}

function fail(msg) {
  console.error(`[transcribe-cli] ERROR: ${msg}`);
  process.exit(1);
}

function run(cmd, opts = {}) {
  const defaults = {
    stdio: VERBOSE ? 'inherit' : 'pipe',
    timeout: 300000, // 5 minutes
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  };
  try {
    return execSync(cmd, { ...defaults, ...opts });
  } catch (err) {
    if (opts.ignoreError) return null;
    throw err;
  }
}

// ── Find Python 3.9+ ────────────────────────────────────

function findPython() {
  const candidates = ['python3.12', 'python3.11', 'python3.10', 'python3.9', 'python3', 'python'];

  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`, {
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: 10000,
      }).toString().trim();

      const [major, minor] = version.split('.').map(Number);
      if (major >= 3 && minor >= 9) {
        log(`Found Python ${version} at ${cmd}`);
        return cmd;
      }
    } catch {
      continue;
    }
  }

  return null;
}

// ── Create Virtual Environment ───────────────────────────

function createVenv(pythonCmd) {
  if (fs.existsSync(VENV_PYTHON)) {
    log('Virtual environment already exists');
    return;
  }

  log('Creating virtual environment...');
  run(`${pythonCmd} -m venv "${VENV_DIR}"`);

  if (!fs.existsSync(VENV_PYTHON)) {
    fail('Failed to create virtual environment');
  }

  // Upgrade pip quietly
  run(`"${VENV_PIP}" install --upgrade pip --quiet`);
}

// ── Install Python Package ──────────────────────────────

function installPackage() {
  log('Installing Python dependencies...');

  // Check if pyproject.toml exists (installed from source)
  const pyproject = path.join(PKG_ROOT, 'pyproject.toml');
  if (fs.existsSync(pyproject)) {
    run(`"${VENV_PIP}" install -e "${PKG_ROOT}" --quiet`);
  } else {
    // Fallback: install from PyPI
    run(`"${VENV_PIP}" install faster-whisper>=1.0.0 ffmpeg-python>=0.2.0 typer>=0.9.0 rich>=13.0.0 pydantic>=2.0.0 pydantic-settings>=2.0.0 python-dotenv>=1.0.0 srt>=3.5.0 --quiet`);
  }

  // Install numpy for live audio support
  run(`"${VENV_PIP}" install numpy --quiet`, { ignoreError: true });

  log('Python dependencies installed');
}

// ── Download Whisper Model ──────────────────────────────

function downloadModel() {
  log(`Pre-downloading Whisper '${DEFAULT_MODEL}' model...`);

  const result = spawnSync(VENV_PYTHON, [
    '-c',
    `
import sys
try:
    from faster_whisper import WhisperModel
    model = WhisperModel('${DEFAULT_MODEL}', device='cpu', compute_type='int8')
    print('ok')
except Exception as e:
    print(f'warn:{e}', file=sys.stderr)
    sys.exit(0)
`,
  ], {
    stdio: ['pipe', 'pipe', 'pipe'],
    timeout: 600000, // 10 minutes for model download
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });

  if (result.status === 0) {
    log(`Whisper '${DEFAULT_MODEL}' model cached`);
  } else {
    const stderr = (result.stderr || '').toString().trim();
    warn(`Model pre-download issue: ${stderr || 'unknown error'}. Model will download on first use.`);
  }
}

// ── Verify Installation ─────────────────────────────────

function verify() {
  try {
    const result = execSync(`"${VENV_PYTHON}" -c "import faster_whisper; print('ok')"`, {
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 10000,
    }).toString().trim();

    if (result === 'ok') {
      log('Installation verified');
      return true;
    }
  } catch {
    // Verification failed
  }
  return false;
}

// ── Main ────────────────────────────────────────────────

function main() {
  // Skip postinstall in CI if TRANSCRIBE_SKIP_POSTINSTALL is set
  if (process.env.TRANSCRIBE_SKIP_POSTINSTALL === '1') {
    log('Skipping postinstall (TRANSCRIBE_SKIP_POSTINSTALL=1)');
    return;
  }

  const pythonCmd = findPython();
  if (!pythonCmd) {
    warn(
      'Python 3.9+ not found. transcribe-cli requires Python.\n' +
      '  Install Python: https://www.python.org/downloads/\n' +
      '  Ubuntu/Debian: sudo apt install python3 python3-venv\n' +
      '  macOS: brew install python@3.12\n\n' +
      '  After installing Python, run: npm rebuild transcribe-cli'
    );
    // Don't fail — allow npm install to complete
    return;
  }

  try {
    createVenv(pythonCmd);
    installPackage();
    downloadModel();

    if (verify()) {
      log('Setup complete. transcribe-cli is ready.');
    } else {
      warn('Setup completed but verification failed. Try: npm rebuild transcribe-cli');
    }
  } catch (err) {
    warn(`Setup encountered an error: ${err.message}`);
    warn('You can retry with: npm rebuild transcribe-cli');
    warn('Or set TRANSCRIBE_VERBOSE=1 to see detailed output.');
    // Don't fail the npm install
  }
}

main();
