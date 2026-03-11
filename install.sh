#!/usr/bin/env bash
# transcribe-cli installer
# One-line install: curl -sSL https://raw.githubusercontent.com/robit-man/transcribe-cli/main/install.sh | bash
set -euo pipefail

REPO_URL="https://github.com/robit-man/transcribe-cli.git"
INSTALL_DIR="${TRANSCRIBE_INSTALL_DIR:-$HOME/.local/share/transcribe-cli}"
BIN_DIR="${HOME}/.local/bin"
VENV_DIR="${INSTALL_DIR}/.venv"
DEFAULT_MODEL="${TRANSCRIBE_MODEL:-base}"

# ── Helpers ──────────────────────────────────────────────

info()  { printf '\033[1;34m[INFO]\033[0m  %s\n' "$*"; }
ok()    { printf '\033[1;32m[OK]\033[0m    %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m  %s\n' "$*"; }
fail()  { printf '\033[1;31m[FAIL]\033[0m  %s\n' "$*"; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

# ── OS Detection ─────────────────────────────────────────

detect_os() {
    case "$(uname -s)" in
        Linux*)  OS="linux" ;;
        Darwin*) OS="macos" ;;
        *)       fail "Unsupported OS: $(uname -s). Only Linux and macOS are supported." ;;
    esac

    if [ "$OS" = "linux" ]; then
        if command_exists apt-get; then
            PKG_MGR="apt"
        elif command_exists dnf; then
            PKG_MGR="dnf"
        elif command_exists pacman; then
            PKG_MGR="pacman"
        else
            PKG_MGR="unknown"
        fi
    elif [ "$OS" = "macos" ]; then
        if command_exists brew; then
            PKG_MGR="brew"
        else
            PKG_MGR="unknown"
        fi
    fi
}

# ── System Dependencies ──────────────────────────────────

install_system_deps() {
    info "Checking system dependencies..."

    # Python 3.9+
    local python_cmd=""
    for cmd in python3.12 python3.11 python3.10 python3.9 python3; do
        if command_exists "$cmd"; then
            local py_version
            py_version=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
            local py_major py_minor
            py_major=$(echo "$py_version" | cut -d. -f1)
            py_minor=$(echo "$py_version" | cut -d. -f2)
            if [ "$py_major" -ge 3 ] && [ "$py_minor" -ge 9 ]; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [ -z "$python_cmd" ]; then
        info "Installing Python 3..."
        case "$PKG_MGR" in
            apt)    sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-venv python3-pip ;;
            dnf)    sudo dnf install -y python3 python3-pip ;;
            pacman) sudo pacman -S --noconfirm python python-pip ;;
            brew)   brew install python@3.12 ;;
            *)      fail "Cannot install Python automatically. Please install Python 3.9+ manually." ;;
        esac
        python_cmd="python3"
    fi
    ok "Python: $($python_cmd --version)"

    # Ensure venv module is available
    if ! "$python_cmd" -c "import venv" 2>/dev/null; then
        info "Installing python3-venv..."
        case "$PKG_MGR" in
            apt) sudo apt-get install -y -qq python3-venv ;;
            *)   ;;  # venv is usually bundled on non-Debian
        esac
    fi

    # FFmpeg
    if ! command_exists ffmpeg; then
        info "Installing FFmpeg..."
        case "$PKG_MGR" in
            apt)    sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg ;;
            dnf)    sudo dnf install -y ffmpeg ;;
            pacman) sudo pacman -S --noconfirm ffmpeg ;;
            brew)   brew install ffmpeg ;;
            *)      fail "Cannot install FFmpeg automatically. Please install it manually." ;;
        esac
    fi
    ok "FFmpeg: $(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')"

    # git
    if ! command_exists git; then
        info "Installing git..."
        case "$PKG_MGR" in
            apt)    sudo apt-get install -y -qq git ;;
            dnf)    sudo dnf install -y git ;;
            pacman) sudo pacman -S --noconfirm git ;;
            brew)   brew install git ;;
            *)      fail "Cannot install git automatically. Please install it manually." ;;
        esac
    fi
    ok "Git: $(git --version | awk '{print $3}')"

    # Export for later use
    PYTHON_CMD="$python_cmd"
}

# ── Clone / Update Repository ────────────────────────────

setup_repo() {
    if [ -d "$INSTALL_DIR/.git" ]; then
        info "Updating existing installation..."
        git -C "$INSTALL_DIR" pull --ff-only 2>/dev/null || {
            warn "Could not pull updates. Reinstalling..."
            rm -rf "$INSTALL_DIR"
            git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
        }
    else
        info "Cloning repository..."
        mkdir -p "$(dirname "$INSTALL_DIR")"
        rm -rf "$INSTALL_DIR"
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
    fi
    ok "Repository ready: $INSTALL_DIR"
}

# ── Python Virtual Environment ───────────────────────────

setup_venv() {
    if [ -d "$VENV_DIR" ]; then
        info "Existing venv found. Upgrading..."
    else
        info "Creating virtual environment..."
        "$PYTHON_CMD" -m venv "$VENV_DIR"
    fi

    # Activate
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    pip install --upgrade pip --quiet

    # Install the package
    info "Installing transcribe-cli and dependencies..."
    pip install -e "$INSTALL_DIR" --quiet

    ok "Python environment ready"
}

# ── Download Default Whisper Model ───────────────────────

download_model() {
    info "Pre-downloading Whisper '${DEFAULT_MODEL}' model (this may take a moment)..."

    "$VENV_DIR/bin/python" -c "
from faster_whisper import WhisperModel
import sys
try:
    model = WhisperModel('${DEFAULT_MODEL}', device='cpu', compute_type='int8')
    print('Model downloaded and verified.')
except Exception as e:
    print(f'Warning: Could not pre-download model: {e}', file=sys.stderr)
    print('The model will be downloaded on first use.', file=sys.stderr)
"
    ok "Whisper '${DEFAULT_MODEL}' model cached"
}

# ── Create CLI Wrapper ───────────────────────────────────

create_wrapper() {
    mkdir -p "$BIN_DIR"

    cat > "$BIN_DIR/transcribe-cli" <<WRAPPER
#!/usr/bin/env bash
# transcribe-cli wrapper — auto-generated by install.sh
exec "${VENV_DIR}/bin/transcribe" "\$@"
WRAPPER
    chmod +x "$BIN_DIR/transcribe-cli"

    # Also create 'transcribe' alias
    cat > "$BIN_DIR/transcribe" <<WRAPPER
#!/usr/bin/env bash
# transcribe wrapper — auto-generated by install.sh
exec "${VENV_DIR}/bin/transcribe" "\$@"
WRAPPER
    chmod +x "$BIN_DIR/transcribe"

    ok "Created commands: transcribe-cli, transcribe"
}

# ── PATH Setup ───────────────────────────────────────────

ensure_path() {
    if echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
        return
    fi

    info "Adding $BIN_DIR to PATH..."

    local shell_rc=""
    case "${SHELL:-/bin/bash}" in
        */zsh)  shell_rc="$HOME/.zshrc" ;;
        */bash) shell_rc="$HOME/.bashrc" ;;
        */fish) shell_rc="$HOME/.config/fish/config.fish" ;;
        *)      shell_rc="$HOME/.profile" ;;
    esac

    local path_line="export PATH=\"$BIN_DIR:\$PATH\""
    if [ "${SHELL:-}" = "*/fish" ]; then
        path_line="set -gx PATH $BIN_DIR \$PATH"
    fi

    if [ -n "$shell_rc" ] && [ -f "$shell_rc" ]; then
        if ! grep -qF "$BIN_DIR" "$shell_rc" 2>/dev/null; then
            echo "" >> "$shell_rc"
            echo "# Added by transcribe-cli installer" >> "$shell_rc"
            echo "$path_line" >> "$shell_rc"
            ok "PATH updated in $shell_rc"
        fi
    fi

    # Also update current session
    export PATH="$BIN_DIR:$PATH"
}

# ── Verify Installation ─────────────────────────────────

verify() {
    info "Verifying installation..."

    if "$BIN_DIR/transcribe" --version >/dev/null 2>&1; then
        local version
        version=$("$BIN_DIR/transcribe" --version 2>&1)
        ok "$version"
    else
        fail "Installation verification failed. Check the output above for errors."
    fi

    "$BIN_DIR/transcribe" setup --check 2>&1 | sed 's/^/  /'
}

# ── Main ─────────────────────────────────────────────────

main() {
    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║     transcribe-cli installer         ║"
    echo "  ║     Local Whisper transcription       ║"
    echo "  ╚══════════════════════════════════════╝"
    echo ""

    detect_os
    info "Detected: $OS ($PKG_MGR)"

    install_system_deps
    setup_repo
    setup_venv
    download_model
    create_wrapper
    ensure_path
    verify

    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║     Installation complete!           ║"
    echo "  ╚══════════════════════════════════════╝"
    echo ""
    echo "  Usage:"
    echo "    transcribe audio.mp3"
    echo "    transcribe video.mkv --format srt"
    echo "    transcribe meeting.wav --model medium --diarize --format json"
    echo "    transcribe batch ./recordings --recursive"
    echo ""
    echo "  If 'transcribe' is not found, restart your shell or run:"
    echo "    export PATH=\"$BIN_DIR:\$PATH\""
    echo ""
}

main "$@"
