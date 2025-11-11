#!/usr/bin/env python3
"""
Build terms.json and terms-dev.json from standards/**/*.yaml
- terms.json = accepted only
- terms-dev.json = accepted + drafts
- Output to build/
- ALPHABETICALLY SORTED by canonical_term (case-insensitive)
- Full metadata matching original JSON
- Clean, modular, one method per section
- Only deletes its own files (not the whole build folder)
"""

import pathlib
import yaml
import json
import shutil

ROOT = pathlib.Path(__file__).parent.parent
STANDARDS = ROOT / "standards"
BUILD = ROOT / "build"

# Create build folder if missing
BUILD.mkdir(exist_ok=True)

# ----------------------------------------------------------------------
# LOAD TERMS FROM FOLDER
# ----------------------------------------------------------------------
def load_terms(folder: str) -> list[dict]:
    terms = []
    folder_path = STANDARDS / folder
    if not folder_path.exists():
        return terms

    for yaml_path in folder_path.glob("*.yaml"):
        meta = yaml.safe_load(yaml_path.read_text())

        # Base term data
        term_data = {
            "id": meta.get("id"),
            "canonical_term": meta.get("term", ""),
            "definition": meta.get("definition", ""),
            "synonyms": meta.get("synonyms", []),
            "relationships": meta.get("relationships", []),
            "prompt_examples": meta.get("prompt_examples", []),
            "examples": meta.get("examples", []),
            "agent_execution": meta.get("agent_execution", {}),
            "status": folder,
            "metadata": {
                "author": "",
                "source_url": meta.get("discussion", ""),
                "version": meta.get("version", "1.0"),
                "date_added": "",
                "registry": "cat-mip.org",
                "term_type": meta.get("categories", [""])[0] if meta.get("categories") else ""
            }
        }

        # Author
        if meta.get("authors"):
            term_data["metadata"]["author"] = meta["authors"][0].get("name", "")

        # date_added from first history entry
        if meta.get("history"):
            term_data["metadata"]["date_added"] = meta["history"][0].get("date", "")

        # Clean empty fields (keep agent_execution even if empty)
        term_data = {k: v for k, v in term_data.items() if v not in (None, "", [], {}) or k in ["agent_execution", "metadata"]}

        terms.append(term_data)

    # ALPHABETICALLY SORTED by canonical_term (case-insensitive)
    terms.sort(key=lambda x: x["canonical_term"].lower())
    return terms

# ----------------------------------------------------------------------
# BUILD JSON FILES
# ----------------------------------------------------------------------
def build_json():
    accepted = load_terms("accepted")
    drafts = load_terms("drafts")
    dev_terms = accepted + drafts

    # ALPHABETICALLY SORTED overall for dev
    dev_terms.sort(key=lambda x: x["canonical_term"].lower())

    # Only delete our own files
    for file in ["terms.json", "terms-dev.json"]:
        path = BUILD / file
        if path.exists():
            path.unlink()

    # Write terms.json (accepted only)
    (BUILD / "terms.json").write_text(json.dumps(accepted, indent=2, ensure_ascii=False) + "\n")

    # Write terms-dev.json (accepted + drafts)
    (BUILD / "terms-dev.json").write_text(json.dumps(dev_terms, indent=2, ensure_ascii=False) + "\n")

    print(f"\nBuilt terms.json ({len(accepted)} accepted terms — sorted)")
    print(f"Built terms-dev.json ({len(dev_terms)} total terms — sorted)")

# ----------------------------------------------------------------------
# RUN
# ----------------------------------------------------------------------
def main():
    build_json()

if __name__ == "__main__":
    main()
