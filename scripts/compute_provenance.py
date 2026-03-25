#!/usr/bin/env python3
"""
Compute cryptographic provenance for guild artifacts.

- content_hash: SHA-256 of canonical YAML (sorted keys, no signatures)
- Ed25519 signature: signing content_hash with agent's private key
- derivation_chain: trace of parent artifacts if derived

Usage:
  python compute_provenance.py /path/to/artifact.yaml [--sign]
"""
import hashlib
import sys
import yaml
from pathlib import Path

def canonicalize_yaml(data: dict) -> bytes:
    """Produce deterministic YAML bytes for hashing (sorted keys, no nulls)."""
    return yaml.dump(
        data,
        sort_keys=True,
        allow_unicode=True,
        explicit_start=True,
        explicit_end=True,
    ).encode("utf-8")

def compute_content_hash(artifact_path: str) -> str:
    """Compute SHA-256 of canonical YAML representation."""
    with open(artifact_path) as f:
        raw = yaml.safe_load(f)
    # Remove signature and content_hash for hashing
    if "provenance" in raw:
        prov = dict(raw["provenance"])
        prov.pop("signature", None)
        prov["content_hash"] = "sha256:__COMPUTING__"
        raw["provenance"] = prov
    canonical = canonicalize_yaml(raw)
    h = hashlib.sha256(canonical).hexdigest()
    return f"sha256:{h}"

def sign_content_hash(content_hash: str, private_key_path: str) -> str:
    """Sign content_hash with Ed25519 private key. Returns base64 signature."""
    try:
        from nacl.signing import SigningKey
    except ImportError:
        print("WARNING: pynacl not installed. Signature not computed.", file=sys.stderr)
        return ""
    
    with open(private_key_path, "rb") as f:
        key_bytes = f.read()
    signing_key = SigningKey(key_bytes)
    signed = signing_key.sign(content_hash.encode("utf-8"))
    import base64
    return f"base64:Ed25519:{base64.b64encode(signed.signature).decode()}"

def main():
    artifact_path = sys.argv[1]
    sign = "--sign" in sys.argv
    
    content_hash = compute_content_hash(artifact_path)
    print(f"content_hash: {content_hash}")
    
    if sign:
        # Look for private key in standard location
        key_path = Path.home() / ".hermes" / "keys" / "agent-ed25519.key"
        if key_path.exists():
            sig = sign_content_hash(content_hash, str(key_path))
            print(f"signature: {sig}")
        else:
            print("signature: null  # no private key found")

if __name__ == "__main__":
    main()
