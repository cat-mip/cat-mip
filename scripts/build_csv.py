#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# CAT-MIP: cat-mip.json --> vendor-ready prompts CSV
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import jsonschema  # optional
except ImportError:
    jsonschema = None

TERMS_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["id", "canonical_term"],
        "properties": {
            "id": {"type": "string"},
            "canonical_term": {"type": "string"},
            "definition": {"type": "string"},
            "synonyms": {"type": "array", "items": {"type": "string"}},
            "relationships": {"type": "array", "items": {"type": "string"}},
            "prompt_examples": {"type": "array", "items": {"type": "string"}},
            "agent_execution": {
                "type": "object",
                "properties": {
                    "interpretation": {"type": "string"},
                    "actions": {"type": "array", "items": {"type": "string"}},
                },
                "additionalProperties": True,
            },
            "expected_outputs": {
                "type": "array",
                "items": {"oneOf": [{"type": "object"}, {"type": "string"}]},
            },
            "metadata": {
                "type": "object",
                "properties": {
                    "author": {"type": "string"},
                    "source_url": {"type": "string"},
                    "version": {"type": "string"},
                    "date_added": {"type": "string"},
                    "registry": {"type": "string"},
                    "term_type": {"type": "string"},
                },
                "additionalProperties": True,
            },
        },
        "additionalProperties": True,
    },
}

def _safe(d: Dict[str, Any], path: str, default=None):
    """Safely navigate nested dictionary paths."""
    cur: Any = d
    for p in path.split("."):
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

def validate_terms(terms: Any) -> None:
    """Validate terms against schema if jsonschema is available."""
    if jsonschema is None:
        return
    jsonschema.validate(terms, TERMS_SCHEMA)

def iter_rows(terms: List[Dict[str, Any]], std_version: str) -> Iterable[Dict[str, str]]:
    """
    Generate CSV rows from terms data.

    Each prompt_example becomes a separate row with:
    - Unique prompt_id
    - Expected output (from expected_outputs or fallback to action_hints)
    - Metadata from the parent term
    """
    for term in terms:
        term_id = (term.get("id") or "").strip()
        name = (term.get("canonical_term") or "").strip()
        if not term_id or not name:
            raise ValueError("Missing required id/canonical_term")
        prompts = term.get("prompt_examples") or []
        exp_list = term.get("expected_outputs") or []
        actions = _safe(term, "agent_execution.actions") or []

        for i, prompt in enumerate(prompts):
            prompt = (prompt or "").strip()
            if not prompt:
                continue

            # Determine expected output from explicit field or fallback
            exp = exp_list[i] if i < len(exp_list) else None
            kind = "unspecified"
            payload: str

            if isinstance(exp, dict):
                kind = "json"
                payload = json.dumps(exp, ensure_ascii=False, separators=(",", ":"))
            elif isinstance(exp, str):
                kind = "text"
                payload = exp
            else:
                # Fallback to action_hints from agent_execution
                kind = "action_hints"
                payload = json.dumps({"action_hints": actions}, ensure_ascii=False, separators=(",", ":"))

            yield {
                "std_version": std_version,
                "term_id": term_id,
                "canonical_term": name,
                "prompt_id": f"{term_id}-p{i+1:02d}",
                "user_prompt": prompt,
                "expected_output_kind": kind,
                "expected_output_payload": payload,
                "author": _safe(term, "metadata.author") or "",
                "date_added": _safe(term, "metadata.date_added") or "",
                "source_url": _safe(term, "metadata.source_url") or "https://cat-mip.org/standard/v1-0/",
            }

def main() -> int:
    ap = argparse.ArgumentParser(description="Export CAT-MIP prompts CSV from cat-mip.json")
    ap.add_argument("--input", dest="in_path", default="cat-mip.json", help="Path to input JSON file")
    ap.add_argument("--outdir", dest="out_dir", default="generated-csvs", help="Output directory")
    ap.add_argument("--outfile", dest="out_file", default=None, help="Optional explicit output filename")
    ap.add_argument("--std-version", dest="std_version", default="v1.0", help="Standard version")
    args = ap.parse_args()

    in_path = Path(args.in_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine output path
    if args.out_file:
        out_path = Path(args.out_file)
    else:
        out_path = out_dir / f"cat-mip-{args.std_version}-prompts.csv"

    # Load and validate terms
    terms = json.loads(in_path.read_text(encoding="utf-8"))
    validate_terms(terms)

    # Generate rows
    rows = list(iter_rows(terms, std_version=args.std_version))

    # Check for duplicates
    seen = set()
    for r in rows:
        rid = r["prompt_id"]
        if rid in seen:
            raise ValueError(f"Duplicate prompt_id: {rid}")
        seen.add(rid)

    # Write CSV
    fieldnames = [
        "std_version","term_id","canonical_term","prompt_id","user_prompt",
        "expected_output_kind","expected_output_payload","author","date_added","source_url"
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"✓ Wrote {len(rows)} prompt rows from {len(terms)} terms -> {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
