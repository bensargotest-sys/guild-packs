#!/usr/bin/env python3
"""
Guild Agent Onboarding Script — Zero to Working Setup (Python)

Run this on a fresh machine with only Python 3.8+ installed.
Sets up the guild-mcp package, generates signing keys, and validates
connectivity with a sample pack (systematic-debugging).

Usage:
    python3 setup-agent.py

Equivalent bash script: setup-agent.sh
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
import venv
from pathlib import Path

# =============================================================================
# Configuration
# =============================================================================

GUILD_MCP_WHEEL_URL = (
    "https://github.com/bensargotest-sys/guild-packs/releases/download/v1.0.0"
    "/guild_mcp-1.0.0-py3-none-any.whl"
)

HOME = Path.home()
VENV_DIR = HOME / ".hermes" / "venv"
KEY_PATH = HOME / ".hermes" / "keys" / "agent-ed25519.key"
GUILD_DIR = HOME / ".hermes" / "guild"
SAMPLE_PACK = "guild://hermes/systematic-debugging"
INDEX_URL = (
    "https://raw.githubusercontent.com/bensargotest-sys/guild-packs/main/index.json"
)
DEFAULT_REPO = "bensargotest-sys/guild-packs"

# =============================================================================
# Output helpers
# =============================================================================

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def info(msg: str) -> None:
    print(f"{BLUE}[INFO]{NC} {msg}")


def success(msg: str) -> None:
    print(f"{GREEN}[OK]{NC}   {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{NC} {msg}")


def error(msg: str) -> None:
    print(f"{RED}[ERR]{NC}  {msg}", file=sys.stderr)


def section(title: str) -> None:
    print("")
    print(f"=== {title} ===")


# =============================================================================
# Step 0: Prerequisites
# =============================================================================

def check_prerequisites() -> bool:
    section("Step 0 — Checking Prerequisites")
    missing = False

    # Python version
    version = sys.version_info
    if version < (3, 8):
        error(f"Python 3.8+ required, found: {version.major}.{version.minor}.{version.micro}")
        missing = True
    else:
        success(f"python3: {version.major}.{version.minor}.{version.micro}")

    # pip
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        pip_ver = result.stdout.strip().split()[1] if result.returncode == 0 else "unknown"
        success(f"pip: {pip_ver}")
    except Exception as e:
        error(f"pip not found or not working: {e}")
        missing = True

    # gh CLI (optional)
    gh_path = shutil.which("gh")
    if gh_path:
        try:
            result = subprocess.run(
                ["gh", "--version"], capture_output=True, text=True, timeout=10,
            )
            gh_ver = result.stdout.split("\n")[0] if result.returncode == 0 else "unknown"
            success(f"gh CLI: {gh_ver}")
        except Exception:
            warn("gh CLI found but could not get version")
    else:
        warn("gh CLI not found — some connectivity checks may be limited")

    if missing:
        error("Missing prerequisites — please install them and re-run this script.")
        return False

    return True


# =============================================================================
# Step 1: Create venv and install guild-mcp
# =============================================================================

def create_venv_and_install() -> Path:
    section("Step 1 — Creating virtual environment and installing guild-mcp")

    if VENV_DIR.exists():
        warn(f"Virtual environment already exists at {VENV_DIR}")
        info("Re-using existing venv (package may already be installed).")
    else:
        info(f"Creating venv at {VENV_DIR} ...")
        venv.create(VENV_DIR, with_pip=True, upgrade_deps=False)
        success("Virtual environment created.")

    pip_path = VENV_DIR / "bin" / "pip"
    info("Upgrading pip ...")
    subprocess.run([str(pip_path), "install", "--upgrade", "pip"],
                   capture_output=True, timeout=120)
    success("pip upgraded.")

    info(f"Installing guild-mcp from GitHub release ...")
    result = subprocess.run(
        [str(pip_path), "install", GUILD_MCP_WHEEL_URL],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        error(f"Failed to install guild-mcp: {result.stderr}")
        sys.exit(1)
    success("guild-mcp installed.")

    return VENV_DIR


# =============================================================================
# Step 2: Generate Ed25519 signing key
# =============================================================================

def generate_signing_key(venv_dir: Path, force: bool = False) -> None:
    section("Step 2 — Generating Ed25519 Signing Key")

    key_path = Path(KEY_PATH)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists() and not force:
        warn(f"Signing key already exists at {key_path}")
        info("Use guild_keygen(force=True) to overwrite.")
        return

    info("Generating Ed25519 signing key ...")
    sys.path.insert(0, str(venv_dir / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"))

    # We need to import from the venv's installed packages
    # Use the venv's python executable directly
    result = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            (
                "from guild_mcp import guild_keygen; "
                f"pub = guild_keygen(force={str(force).lower()}); "
                "print(pub)"
            ),
        ],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "PYTHONPATH": str(venv_dir / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages")},
    )

    if result.returncode != 0:
        error(f"Key generation failed: {result.stderr}")
        sys.exit(1)

    public_key = result.stdout.strip()
    success(f"Signing key generated at {key_path}")
    info(f"Public key: {public_key}")


# =============================================================================
# Step 3: Pull pack index and verify connectivity
# =============================================================================

def verify_connectivity(venv_dir: Path) -> None:
    section("Step 3 — Pulling Pack Index and Verifying Connectivity")

    # gh CLI check
    gh_path = shutil.which("gh")
    if gh_path:
        info("Testing GitHub API connectivity ...")
        result = subprocess.run(
            ["gh", "api", "repos/bensargotest-sys/guild-packs", "--jq", ".full_name"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            success(f"GitHub API reachable: {result.stdout.strip()}")
        else:
            warn(f"GitHub API check failed — you may need to run: gh auth login")
    else:
        info("Skipping gh CLI check (not installed)")

    # Fetch index.json
    info("Fetching pack index from GitHub raw ...")
    try:
        with urllib.request.urlopen(INDEX_URL, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        pack_count = len(data.get("packs", []))
        success(f"Pack index fetched: {pack_count} packs indexed")
    except Exception as e:
        error(f"Failed to fetch pack index: {e}")
        sys.exit(1)


# =============================================================================
# Step 4: Pull sample pack and run guild_try
# =============================================================================

def try_sample_pack(venv_dir: Path) -> None:
    section("Step 4 — Pulling Sample Pack and Running guild_try")

    # Set PYTHONPATH so the venv's guild_mcp is importable
    site_packages = venv_dir / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    env = {**os.environ, "PYTHONPATH": str(site_packages)}

    pack_env = {**env, "PYTHONPATH": str(site_packages)}

    info(f"Pulling pack: {SAMPLE_PACK}")
    result = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            f"from guild_mcp import guild_pull; result = guild_pull('{SAMPLE_PACK}'); print(result)",
        ],
        capture_output=True, text=True, timeout=60, env=pack_env,
    )
    if result.returncode != 0:
        warn(f"guild_pull had issues (non-fatal): {result.stderr or result.stdout}")
    else:
        out = result.stdout.strip()
        if "error" in out.lower() or "exception" in out.lower():
            warn(f"guild_pull output: {out[:300]}")
        else:
            success("Pack pulled successfully")

    info(f"Running guild_try (preview without saving) ...")
    result = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            f"from guild_mcp import guild_try_handler; result = guild_try_handler('{SAMPLE_PACK}'); print(result)",
        ],
        capture_output=True, text=True, timeout=60, env=pack_env,
    )
    if result.returncode != 0:
        warn(f"guild_try had issues: {result.stderr or result.stdout}")
    else:
        out = result.stdout.strip()
        success("guild_try completed successfully")
        snippet = out[:500] + "..." if len(out) > 500 else out
        info(f"Preview output: {snippet}")


# =============================================================================
# Step 5: Verify installation layout
# =============================================================================

def verify_layout() -> None:
    section("Step 5 — Verifying Installation Layout")

    dirs_to_check = [
        HOME / ".hermes",
        HOME / ".hermes" / "keys",
        HOME / ".hermes" / "guild",
    ]

    for d in dirs_to_check:
        if d.exists():
            success(f"{d} exists")
        else:
            warn(f"{d} does not exist yet (will be created on first use)")

    if Path(KEY_PATH).exists():
        success(f"Signing key: {KEY_PATH}")
    else:
        warn(f"Signing key not found at expected path")


# =============================================================================
# Print success message
# =============================================================================

def print_success() -> None:
    section("Setup Complete!")
    print("")
    print(f"{GREEN}Your agent is fully set up with the guild.{NC}")
    print("")
    print("Key paths:")
    print(f"  Signing key:  {KEY_PATH}")
    print(f"  Pack storage:  {HOME}/.hermes/guild/")
    print(f"  Executions:    {HOME}/.hermes/guild/executions/")
    print(f"  Virtual env:   {VENV_DIR}")
    print("")
    print("Next steps:")
    print(f"  1. Activate the venv:   source {VENV_DIR}/bin/activate")
    print(f"  2. Search packs:         guild-mcp  (then use tools/call guild_search)")
    print(f"  3. Pull a pack:          Use guild_pull('guild://hermes/<pack-name>')")
    print(f"  4. Try a pack:           Use guild_try('guild://hermes/<pack-name>')")
    print(f"  5. Apply a pack:         Use guild_apply_start('<pack-name>', '<task>')")
    print("")
    print("Python API (in any script):")
    print("  from guild_mcp.client import GuildMCPClient, search, pull, try_pack")
    print("  result = search('debugging')")
    print("  result = pull('guild://hermes/systematic-debugging')")
    print("  result = try_pack('guild://hermes/systematic-debugging')")
    print("")
    print("MCP client config (for Claude Code / other MCP hosts):")
    mcp_config = '{{"mcpServers": {{"guild": {{"command": "{VENV}/bin/guild-mcp"}}}}}}'
    print(f"  {mcp_config.format(VENV=VENV_DIR)}")
    print("")
    print("For MCP server stdio mode (run directly):")
    print(f"  {VENV_DIR}/bin/guild-mcp")
    print("")


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    print("")
    print("=" * 60)
    print("  Guild Agent Onboarding — Zero to Working Setup (Python)")
    print("=" * 60)

    if not check_prerequisites():
        sys.exit(1)

    venv_dir = create_venv_and_install()
    generate_signing_key(venv_dir)
    verify_connectivity(venv_dir)
    try_sample_pack(venv_dir)
    verify_layout()
    print_success()


if __name__ == "__main__":
    main()
