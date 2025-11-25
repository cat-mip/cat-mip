#!/usr/bin/env python3
"""
verify-unique-ids.py
Ensure no two CAT-MIP YAML files share the same 'id:' value.

Works on:
  standards/accepted/*.yaml
  standards/draft/*.yaml
  standards/proposed/*.yaml (if you add it later)

Features:
- Exact same style as build-cat-mip.py
- Reports duplicates with relative paths (just like GitHub)
- Also reports files missing an 'id:' field
- Exits with status 1 on duplicates → perfect for CI/CD and pre-commit
"""

import pathlib
import re
import sys
from collections import defaultdict

# ----------------------------------------------------------------------
# PATHS — same as your build script
# ----------------------------------------------------------------------
ROOT = pathlib.Path(__file__).parent.parent
STANDARDS = ROOT / "standards"

# Regex: matches  id: 'CAT-MIP-000000025'  or  id: CAT-MIP-000000025
ID_REGEX = re.compile(r'^\s*id\s*:\s*[\'"`]?([^\'"` ]+)[\'"`]?', re.MULTILINE)


# ----------------------------------------------------------------------
# EXTRACT ID FROM A SINGLE FILE
# ----------------------------------------------------------------------
def extract_id_from_file(file_path: pathlib.Path) -> str | None:
    """Return the ID string or None if not found / malformed."""
    try:
        content = file_path.read_text(encoding="utf-8")
        match = ID_REGEX.search(content)
        return match.group(1).strip() if match else None
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return None


# ----------------------------------------------------------------------
# SCAN ALL YAML FILES UNDER standards/**
# ----------------------------------------------------------------------
def scan_all_terms() -> tuple[defaultdict[list], list[pathlib.Path]]:
    """
    Returns:
        id_to_files: dict[id → list of Path]
        missing_id_files: list of files without any id: field
    """
    id_to_files = defaultdict(list)
    missing_id_files = []

    if not STANDARDS.exists():
        print(f"Error: standards/ directory not found at {STANDARDS}")
        sys.exit(1)

    for yaml_path in STANDARDS.rglob("*.yaml"):
        if not yaml_path.is_file():
            continue

        term_id = extract_id_from_file(yaml_path)
        if term_id is None:
            missing_id_files.append(yaml_path)
        else:
            id_to_files[term_id].append(yaml_path)

    return id_to_files, missing_id_files


# ----------------------------------------------------------------------
# MAIN CHECK & REPORT
# ----------------------------------------------------------------------
def main():
    print("Verifying uniqueness of 'id:' fields across all CAT-MIP terms...\n")

    id_to_files, missing = scan_all_terms()

    # --- Report duplicates ------------------------------------------------
    duplicates = {tid: paths for tid, paths in id_to_files.items() if len(paths) > 1}

    if duplicates:
        print("FOUND DUPLICATE IDs\n")
        for term_id, paths in sorted(duplicates.items()):
            print(f"Duplicate ID: '{term_id}'")
            for p in sorted(paths):
                # Show path relative to repo root — clean and GitHub-friendly
                print(f"   → {p.relative_to(ROOT)}")
            print()
        print(f"{len(duplicates)} duplicate ID(s) found.")
        sys.exit(1)

    # --- Report missing IDs (warning only) --------------------------------
    if missing:
        print("WARNING: Files missing 'id:' field")
        for p in sorted(missing):
            print(f"   → {p.relative_to(ROOT)}")
        print()

    total_files = sum(len(paths) for paths in id_to_files.values()) + len(missing)
    unique_ids = len(id_to_files)

    print(f"All {unique_ids} IDs are unique across {total_files} YAML files.")
    sys.exit(0)

# ----------------------------------------------------------------------
# RUN
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
