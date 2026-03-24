#!/usr/bin/env python3
"""Validate all YAML pack files in packs/ and feedback/ directories."""

import glob
import sys
import yaml

REQUIRED_FIELDS = {"type", "version", "id", "problem_class", "phases", "provenance"}
VALID_CONFIDENCE = {"guessed", "inferred", "tested", "validated"}
FEEDBACK_FIELDS = {"parent_artifact", "before", "after"}

errors = []
files_checked = 0


def validate_file(path):
    global files_checked
    files_checked += 1
    file_errors = []

    # 1. Valid YAML
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        file_errors.append(f"  Invalid YAML: {e}")
        return file_errors

    if not isinstance(data, dict):
        file_errors.append("  Not a YAML mapping (expected key-value pairs)")
        return file_errors

    # 2. Required fields
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        file_errors.append(f"  Missing required fields: {', '.join(sorted(missing))}")

    # 3. Provenance confidence
    prov = data.get("provenance")
    if isinstance(prov, dict):
        conf = prov.get("confidence")
        if conf and conf not in VALID_CONFIDENCE:
            file_errors.append(
                f"  Invalid provenance.confidence: '{conf}' "
                f"(must be one of: {', '.join(sorted(VALID_CONFIDENCE))})"
            )
    elif "provenance" in data:
        file_errors.append("  provenance must be a mapping with a 'confidence' key")

    # 4. Phases is non-empty list
    phases = data.get("phases")
    if phases is not None:
        if not isinstance(phases, list) or len(phases) == 0:
            file_errors.append("  'phases' must be a non-empty list")

    # 5. Feedback type checks
    doc_type = data.get("type", "")
    if "feedback" in str(doc_type).lower() or "feedback/" in path:
        fb_missing = FEEDBACK_FIELDS - set(data.keys())
        if fb_missing:
            file_errors.append(
                f"  Feedback pack missing fields: {', '.join(sorted(fb_missing))}"
            )

    return file_errors


def main():
    paths = sorted(
        glob.glob("packs/**/*.yaml", recursive=True)
        + glob.glob("packs/**/*.yml", recursive=True)
        + glob.glob("feedback/**/*.yaml", recursive=True)
        + glob.glob("feedback/**/*.yml", recursive=True)
    )

    if not paths:
        print("No .yaml/.yml files found in packs/ or feedback/.")
        print("PASSED (nothing to validate)")
        return 0

    for path in paths:
        file_errors = validate_file(path)
        if file_errors:
            errors.append((path, file_errors))

    # Report
    print(f"Checked {files_checked} file(s)\n")

    if errors:
        print(f"FAILED - {len(errors)} file(s) with errors:\n")
        for path, errs in errors:
            print(f"{path}:")
            for e in errs:
                print(e)
            print()
        return 1
    else:
        print("ALL PASSED - every pack file is valid.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
