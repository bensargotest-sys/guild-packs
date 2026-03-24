#!/usr/bin/env python3
"""Generate index.json from packs/ and feedback/ YAML files."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


def parse_pack(filepath: Path) -> dict:
    """Parse a pack YAML file into an index entry."""
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return None

    pack_id = data.get("id", "")
    name = pack_id.split("/")[-1] if "/" in pack_id else filepath.stem
    phases = data.get("phases", [])
    phase_names = [p.get("name", "") for p in phases if isinstance(p, dict)]
    provenance = data.get("provenance", {}) or {}

    return {
        "id": pack_id,
        "name": name,
        "problem_class": data.get("problem_class", ""),
        "confidence": provenance.get("confidence", "unknown"),
        "phases": len(phases),
        "phase_names": phase_names,
        "version": data.get("version", "1.0.0"),
    }


def parse_feedback(filepath: Path) -> dict:
    """Parse a feedback YAML file into an index entry."""
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return None

    return {
        "id": data.get("id", filepath.stem),
        "parent_artifact": data.get("parent_artifact", ""),
        "outcome": data.get("outcome", "unknown"),
    }


def main():
    repo_root = Path(os.environ.get("REPO_ROOT", "."))

    packs_dir = repo_root / "packs"
    feedback_dir = repo_root / "feedback"

    packs = []
    feedback = []

    # Scan packs/
    if packs_dir.exists():
        for f in sorted(packs_dir.glob("*.yaml")):
            entry = parse_pack(f)
            if entry:
                packs.append(entry)
        for f in sorted(packs_dir.glob("*.yml")):
            entry = parse_pack(f)
            if entry:
                packs.append(entry)

    # Scan feedback/
    if feedback_dir.exists():
        for f in sorted(feedback_dir.glob("*.yaml")):
            entry = parse_feedback(f)
            if entry:
                feedback.append(entry)
        for f in sorted(feedback_dir.glob("*.yml")):
            entry = parse_feedback(f)
            if entry:
                feedback.append(entry)

    index = {
        "packs": packs,
        "feedback": feedback,
        "updated": datetime.now(timezone.utc).isoformat(),
    }

    output_path = repo_root / "index.json"
    with open(output_path, "w") as f:
        json.dump(index, f, indent=2)

    print(f"Generated index.json: {len(packs)} packs, {len(feedback)} feedback entries")


if __name__ == "__main__":
    main()
