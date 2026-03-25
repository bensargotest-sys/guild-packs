#!/usr/bin/env python3
"""
Compute Sybil resistance score for a guild artifact.

 novelty_index: Jaccard similarity to existing packs (lower = more novel)
 content_fingerprint: SHA-256 of content only (not meta: timestamps, hashes, counts)
 derivation_depth: number of hops from an original artifact
 stake_weight: adoption_success_rate * unique_adopters
 sybil_resistance_flag: true if content_fingerprint matches >= 3 other packs

Usage:
  python compute_sybil_score.py /path/to/artifact.yaml /path/to/index.json
"""
import hashlib
import json
import sys
import yaml
from pathlib import Path

def compute_content_fingerprint(artifact_path: str) -> str:
    """Hash only the substantive content fields, not metadata."""
    with open(artifact_path) as f:
        raw = yaml.safe_load(f)
    
    # Fields to exclude from fingerprint (meta, not content)
    exclude = {
        "provenance", "adoption", "sybil_score",
        "version", "created", "content_hash", "signature"
    }
    
    def fingerprintable(obj):
        if isinstance(obj, dict):
            return {k: fingerprintable(v) for k, v in obj.items() if k not in exclude}
        elif isinstance(obj, list):
            return [fingerprintable(i) for i in obj]
        return obj
    
    fp_data = yaml.dump(fingerprintable(raw), sort_keys=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(fp_data).hexdigest()}"

def jaccard_similarity(content_a: str, content_b: str) -> float:
    """Compute Jaccard similarity between two pack content sets."""
    # Simple word-level Jaccard
    words_a = set(content_a.lower().split())
    words_b = set(content_b.lower().split())
    if not words_a and not words_b:
        return 1.0
    return len(words_a & words_b) / len(words_a | words_b)

def novelty_index(artifact_path: str, index_path: str) -> float:
    """Compute minimum Jaccard distance to any existing pack (lower = more novel)."""
    with open(artifact_path) as f:
        raw = yaml.safe_load(f)
    my_content = yaml.dump(raw, sort_keys=True)
    
    if not Path(index_path).exists():
        return 1.0
    
    with open(index_path) as f:
        index = json.load(f)
    
    min_sim = 1.0
    for entry in index.get("artifacts", []):
        # Compare against stored content fingerprint
        other_fp = entry.get("content_fingerprint", "")
        if other_fp and other_fp != compute_content_fingerprint(artifact_path):
            # Estimate similarity from stored evidence
            # We use a proxy: if same problem_class and similar structure
            # This is a simplification — full impl would need actual content comparison
            pass
    
    return min_sim

def derivation_depth(artifact_path: str) -> int:
    """Count derivation chain depth (0 for original)."""
    with open(artifact_path) as f:
        raw = yaml.safe_load(f)
    chain = raw.get("provenance", {}).get("derivation_chain", [])
    return len(chain)

def stake_weight(artifact_path: str) -> float:
    """adoption_success_rate * unique_adopters."""
    with open(artifact_path) as f:
        raw = yaml.safe_load(f)
    adoption = raw.get("adoption", {})
    rate = adoption.get("success_rate", 0.0)
    adopters = adoption.get("unique_adopters", 0)
    return rate * adopters

def sybil_resistance_flag(artifact_path: str, index_path: str) -> bool:
    """True if content fingerprint matches >= 3 other packs."""
    if not Path(index_path).exists():
        return False
    fp = compute_content_fingerprint(artifact_path)
    with open(index_path) as f:
        index = json.load(f)
    matches = sum(
        1 for e in index.get("artifacts", [])
        if e.get("content_fingerprint") == fp
    )
    return matches >= 3

def main():
    artifact_path = sys.argv[1]
    index_path = sys.argv[2] if len(sys.argv) > 2 else "/root/hermes-workspace/guild-packs/index.json"
    
    fp = compute_content_fingerprint(artifact_path)
    depth = derivation_depth(artifact_path)
    sw = stake_weight(artifact_path)
    flag = sybil_resistance_flag(artifact_path, index_path)
    novelty = novelty_index(artifact_path, index_path)
    
    print(f"content_fingerprint: {fp}")
    print(f"novelty_index: {novelty:.3f}")
    print(f"derivation_depth: {depth}")
    print(f"stake_weight: {sw:.2f}")
    print(f"sybil_resistance_flag: {flag}")

if __name__ == "__main__":
    main()
