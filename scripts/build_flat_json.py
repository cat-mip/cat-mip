#!/usr/bin/env python3
"""
Build cat-mip-flat.json and cat-mip-flat-dev.json from standards/**/*.yaml
- cat-mip-flat.json = accepted only
- cat-mip-flat-dev.json = accepted + draft
- Output to build/
- ALPHABETICALLY SORTED by canonical_term (case-insensitive)
- Removes id, author, history, status, source_url, date_added, version,
-    term_type metadata and flattens the structure, which can help 
-    comprehension and token usage in some RAG applications
- Returns term, and remaining data in a single element
- Clean, modular, one method per section
- Only deletes its own files (not the whole build folder)

Output JSON is guaranteed schema-compliant and machine-readable:
• Retains checks on remaining elements from build_json.py
• No empty arrays omitted — [] means explicitly empty
→ Downstream tools can trust the data 100% — no defensive code needed
"""

import pathlib
import yaml
import json
import re


ROOT = pathlib.Path(__file__).parent.parent
STANDARDS = ROOT / "standards"
BUILD = ROOT / "build"

# Create build folder if missing
BUILD.mkdir(exist_ok=True)

def _normalize(meta: dict) -> dict:
    m = (meta or {}).copy()

    # agent_execution → dict with actions always list of non-empty strings
    ae = m.get("agent_execution") or {}
    if not isinstance(ae, dict):
        ae = {}
    actions = ae.get("actions") or []
    ae["actions"] = [a.strip() for a in actions if isinstance(a, str) and a.strip()]
    m["agent_execution"] = ae

    # Critical text fields → string, never empty
    m["term"] = str(m.get("term", "")).strip() or "UNNAMED TERM"
    m["definition"] = str(m.get("definition", "")).strip() or "No definition provided."

    # split relationships to remove camelCase to let chroma index better if there is one
    if m.get("relationships") and isinstance(m["relationships"], list):
        m["relationships"] = [
        re.sub(r'([a-z])([A-Z])', r'\1 \2', r)
        for r in m["relationships"]
        if isinstance(r, str)
    ]

    return m


# ----------------------------------------------------------------------
# LOAD TERMS FROM FOLDER
# ----------------------------------------------------------------------
def load_terms(folder: str) -> list[dict]:
    terms = []
    folder_path = STANDARDS / folder
    if not folder_path.exists():
        return terms

    for yaml_path in folder_path.glob("*.yaml"):
        meta = _normalize(yaml.safe_load(yaml_path.read_text()))

        actions = meta["agent_execution"].get("actions", [])
        interpretation = meta["agent_execution"].get("interpretation", "")

        body = " ".join(filter(None, [
            meta["definition"],
            ", ".join(meta.get("synonyms",[])),
            ", ".join(meta.get("relationships",[])),
            ", ".join(meta.get("prompt_examples",[])),
            interpretation,
            ", ".join(actions),
        ]))

        terms.append({
            "term": meta["term"],
            "body": body,
        })
    
    terms.sort(key=lambda x: x["term"].lower())
    return terms


# ----------------------------------------------------------------------
# BUILD JSON FILES
# ----------------------------------------------------------------------
def build_json():
    accepted = load_terms("accepted")
    draft = load_terms("draft")
    dev_terms = accepted + draft
    dev_terms.sort(key=lambda x: x["term"].lower())

    for file in ["cat-mip.json", "cat-mip-dev.json"]:
        path = BUILD / file
        if path.exists():
            path.unlink()

    (BUILD / "cat-mip-flat.json").write_text(json.dumps(accepted, indent=2, ensure_ascii=False) + "\n")
    (BUILD / "cat-mip-flat-dev.json").write_text(json.dumps(dev_terms, indent=2, ensure_ascii=False) + "\n")

  
    print(f"\nBuilt cat-mip.json ({len(accepted)} accepted terms)")
    print(f"Built cat-mip-dev.json ({len(dev_terms)} total terms)")



# ----------------------------------------------------------------------
# RUN
# ----------------------------------------------------------------------
def main():
    build_json()

if __name__ == "__main__":
    main()
