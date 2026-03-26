#!/usr/bin/env bash
# =============================================================================
# Guild Agent Onboarding Script — Zero to Working Setup
# =============================================================================
# Run this on a fresh machine with only Python 3.8+ installed.
# Sets up the guild-mcp package, generates signing keys, and validates
# connectivity with a sample pack (systematic-debugging).
#
# Usage:
#   chmod +x setup-agent.sh && ./setup-agent.sh
#
# Prerequisites checked: python3, pip, gh CLI
# =============================================================================

set -euo pipefail

# ---- Configuration --------------------------------------------------------
GUILD_MCP_WHEEL_URL="https://github.com/bensargotest-sys/guild-packs/releases/download/v1.0.0/guild_mcp-1.0.0-py3-none-any.whl"
VENV_DIR="${HOME}/.hermes/venv"
KEY_PATH="${HOME}/.hermes/keys/agent-ed25519.key"
GUILD_DIR="${HOME}/.hermes/guild"
SAMPLE_PACK="guild://hermes/systematic-debugging"
INDEX_URL="https://raw.githubusercontent.com/bensargotest-sys/guild-packs/main/index.json"

# ---- Colors for output ----------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERR]${NC}  $1"; }
section() { echo ""; echo "=== $1 ==="; }

# ---- Helper: check command exists ------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }

# ---- Step 0: Pre-flight checks --------------------------------------------
section "Step 0 — Checking Prerequisites"

MISSING=0

if have python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]; }; then
        error "Python 3.8+ required, found: $PYTHON_VERSION"
        MISSING=1
    else
        success "python3: $PYTHON_VERSION"
    fi
else
    error "python3 not found — please install Python 3.8 or later"
    MISSING=1
fi

if have pip; then
    success "pip: $(pip --version 2>&1 | awk '{print $2}')"
else
    error "pip not found"
    MISSING=1
fi

if have gh; then
    success "gh CLI: $(gh --version 2>&1 | head -1)"
else
    warn "gh CLI not found — some connectivity checks may be limited"
fi

if [ $MISSING -eq 1 ]; then
    error "Missing prerequisites — please install them and re-run this script."
    exit 1
fi

# ---- Step 1: Create venv and install guild-mcp ----------------------------
section "Step 1 — Creating virtual environment and installing guild-mcp"

info "Creating venv at ${VENV_DIR}..."
python3 -m venv "$VENV_DIR"
success "Virtual environment created."

info "Upgrading pip..."
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1

info "Installing guild-mcp from GitHub release..."
"$VENV_DIR/bin/pip" install "$GUILD_MCP_WHEEL_URL" >/dev/null 2>&1
success "guild-mcp installed."

# ---- Step 2: Generate Ed25519 signing key --------------------------------
section "Step 2 — Generating Ed25519 Signing Key"

info "Ensuring keys directory exists..."
mkdir -p "$(dirname "$KEY_PATH")"

if [ -f "$KEY_PATH" ]; then
    warn "Signing key already exists at $KEY_PATH"
    read -p "Overwrite it? [y/N] " -r REPLY
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Keeping existing key."
    else
        info "Generating new Ed25519 signing key..."
        "$VENV_DIR/bin/python" -c "
from guild_mcp import guild_keygen
pub = guild_keygen(force=True)
print(pub)
"
        success "New signing key generated."
    fi
else
    info "Generating Ed25519 signing key..."
    KEYGEN_OUTPUT=$("$VENV_DIR/bin/python" -c "
from guild_mcp import guild_keygen
pub = guild_keygen(force=False)
print(pub)
")
    success "Signing key generated at $KEY_PATH"
    info "Public key: $KEYGEN_OUTPUT"
fi

# ---- Step 3: Pull pack index and verify connectivity ----------------------
section "Step 3 — Pulling Pack Index and Verifying Connectivity"

info "Testing GitHub API connectivity..."
if have gh; then
    if gh api repos/bensargotest-sys/guild-packs --jq '.full_name' >/dev/null 2>&1; then
        success "GitHub API reachable (bensargotest-sys/guild-packs)"
    else
        warn "GitHub API check failed — you may need to run: gh auth login"
    fi
else
    info "Skipping gh CLI check (not installed)"
fi

info "Fetching pack index from GitHub raw..."
INDEX_FETCH=$("$VENV_DIR/bin/python" -c "
import urllib.request
import json
url = 'https://raw.githubusercontent.com/bensargotest-sys/guild-packs/main/index.json'
try:
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read())
        print(f'OK: {len(data.get(\"packs\", []))} packs indexed')
except Exception as e:
    print(f'FAIL: {e}')
    exit(1)
" 2>&1)
if echo "$INDEX_FETCH" | grep -q "^OK:"; then
    success "$(echo "$INDEX_FETCH" | sed 's/^OK: //')"
else
    error "Failed to fetch index: $INDEX_FETCH"
    exit 1
fi

# ---- Step 4: Pull systematic-debugging pack and run guild_try --------------
section "Step 4 — Pulling Sample Pack and Running guild_try"

info "Pulling pack: $SAMPLE_PACK"
PULL_OUTPUT=$("$VENV_DIR/bin/python" -c "
from guild_mcp import guild_pull
result = guild_pull('$SAMPLE_PACK')
print(result)
" 2>&1)
if echo "$PULL_OUTPUT" | grep -qi "error\|fail\|exception"; then
    warn "guild_pull had issues (non-fatal): $PULL_OUTPUT"
else
    success "Pack pulled successfully"
fi

info "Running guild_try (preview without saving)..."
TRY_OUTPUT=$("$VENV_DIR/bin/python" -c "
from guild_mcp import guild_try_handler
result = guild_try_handler('$SAMPLE_PACK')
print(result)
" 2>&1)
if echo "$TRY_OUTPUT" | grep -qi "error\|fail\|exception"; then
    warn "guild_try had issues: $TRY_OUTPUT"
else
    success "guild_try completed successfully"
    # Show a summary snippet if it's short
    if [ ${#TRY_OUTPUT} -lt 500 ]; then
        info "Preview output: $TRY_OUTPUT"
    else
        info "Preview output (truncated): ${TRY_OUTPUT:0:500}..."
    fi
fi

# ---- Step 5: Verify directories -------------------------------------------
section "Step 5 — Verifying Installation Layout"

check_dir() {
    if [ -d "$1" ]; then
        success "$1 exists"
    else
        warn "$1 does not exist yet (will be created on first use)"
    fi
}

check_dir "$HOME/.hermes"
check_dir "$HOME/.hermes/keys"
check_dir "$HOME/.hermes/guild"

if [ -f "$KEY_PATH" ]; then
    success "Signing key: $KEY_PATH"
else
    warn "Signing key not found at expected path"
fi

# ---- Done -----------------------------------------------------------------
section "Setup Complete!"

echo ""
echo -e "${GREEN}Your agent is fully set up with the guild.${NC}"
echo ""
echo "Key paths:"
echo "  Signing key:  $KEY_PATH"
echo "  Pack storage:  $HOME/.hermes/guild/"
echo "  Executions:    $HOME/.hermes/guild/executions/"
echo "  Virtual env:   $VENV_DIR"
echo ""
echo "Next steps:"
echo "  1. Activate the venv:   source $VENV_DIR/bin/activate"
echo "  2. Search packs:         guild-mcp  (then use tools/call guild_search)"
echo "  3. Pull a pack:          Use guild_pull('guild://hermes/<pack-name>')"
echo "  4. Try a pack:           Use guild_try('guild://hermes/<pack-name>')"
echo "  5. Apply a pack:         Use guild_apply_start('<pack-name>', '<task>')"
echo ""
echo "Python API (in any script):"
echo "  from guild_mcp.client import GuildMCPClient, search, pull, try_pack"
echo "  result = search('debugging')"
echo "  result = pull('guild://hermes/systematic-debugging')"
echo "  result = try_pack('guild://hermes/systematic-debugging')"
echo ""
echo "MCP client config (for Claude Code / other MCP hosts):"
echo "  {\"mcpServers\": {\"guild\": {\"command\": \"$VENV_DIR/bin/guild-mcp\"}}}"
echo ""
echo "For MCP server stdio mode (run directly):"
echo "  $VENV_DIR/bin/guild-mcp"
echo ""
