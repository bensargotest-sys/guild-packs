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

    pack_type = data.get("type", "")
    pack_id = data.get("id", "")
    name = pack_id.split("/")[-1] if "/" in pack_id else filepath.stem
    provenance = data.get("provenance", {}) or {}

    # Workflow packs have phases; rubrics have criteria
    if pack_type == "workflow_pack":
        phases = data.get("phases", [])
        phase_names = [p.get("name", "") for p in phases if isinstance(p, dict)]
        tier = _infer_tier(provenance.get("confidence", "guessed"))
        return {
            "id": pack_id,
            "name": name,
            "type": pack_type,
            "problem_class": data.get("problem_class", ""),
            "mental_model": data.get("mental_model", ""),
            "confidence": provenance.get("confidence", "unknown"),
            "tier": tier,
            "phase_count": len(phases),
            "phase_names": phase_names,
            "version": data.get("version", "1.0.0"),
        }
    elif pack_type == "critique_rubric":
        criteria = data.get("criteria", [])
        tier = _infer_tier(provenance.get("confidence", "guessed"))
        return {
            "id": pack_id,
            "name": name,
            "type": pack_type,
            "domain": data.get("domain", ""),
            "criteria_count": len(criteria) if isinstance(criteria, list) else 0,
            "confidence": provenance.get("confidence", "unknown"),
            "tier": tier,
            "version": data.get("version", "1.0.0"),
        }
    else:
        # Generic fallback
        return {
            "id": pack_id,
            "name": name,
            "type": pack_type,
            "confidence": provenance.get("confidence", "unknown"),
            "version": data.get("version", "1.0.0"),
        }


def _infer_tier(confidence: str) -> str:
    """Map confidence level to display tier."""
    mapping = {
        "guessed": "EXPERIMENTAL",
        "inferred": "COMMUNITY",
        "tested": "VALIDATED",
        "validated": "VALIDATED",
    }
    return mapping.get(confidence, "COMMUNITY")


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
    examples_dir = repo_root / "examples"

    packs = []
    feedback = []
    examples = []

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

    # Scan examples/
    if examples_dir.exists():
        for f in sorted(examples_dir.glob("*.yaml")):
            entry = parse_pack(f)
            if entry:
                examples.append(entry)
        for f in sorted(examples_dir.glob("*.yml")):
            entry = parse_pack(f)
            if entry:
                examples.append(entry)

    index = {
        "packs": packs,
        "feedback": feedback,
        "examples": examples,
        "updated": datetime.now(timezone.utc).isoformat(),
    }

    output_path = repo_root / "index.json"
    with open(output_path, "w") as f:
        json.dump(index, f, indent=2)

    print(f"Generated index.json: {len(packs)} packs, {len(feedback)} feedback entries, {len(examples)} examples")


if __name__ == "__main__":
    main()
