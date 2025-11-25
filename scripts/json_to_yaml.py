#!/usr/bin/env python3
"""
CAT-MIP YAML Converter — FINAL & BLOG-COMPLIANT
- Single quotes preferred
- Double quotes only when needed
- No trailing colon
- Perfect YAML
"""

import json
import pathlib
import re
import textwrap

ROOT = pathlib.Path(__file__).parent.parent
INPUT_JSON = ROOT / "terms.json"
STANDARDS = ROOT / "standards"

for folder in ["accepted", "draft", "deprecated", "rejected"]:
    (STANDARDS / folder).mkdir(parents=True, exist_ok=True)

AUTHOR_ORG = {
    "Nicole Reineke": "N-able",
    "Roop Petersen": "Auvik Networks Inc."
}

def term_to_filename(term: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', term.strip().lower()).strip('-') + ".yaml"

def get_short_id(full_id: str) -> str:
    parts = full_id.split('-') if full_id else []
    if len(parts) == 4 and parts[0] == 'CAT' and parts[1] == 'MIP':
        return f"CAT-MIP-{parts[3]}"
    return full_id

def clean_quotes(value):
    if not isinstance(value, str):
        return value
    replacements = {
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
        "\u2013": "-", "\u2014": "--", "\u2026": "..."
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    return value

def needs_quotes(s: str) -> bool:
    if not isinstance(s, str):
        return False
    return any(c in s for c in ":{}[]&*#?|-<>=!%@,") or \
           s.startswith((' ', '\t')) or s.endswith((' ', '\t')) or \
           '\n' in s

def yaml_scalar(value, max_width=90):
    cleaned = clean_quotes(value)
    if isinstance(cleaned, (int, float, bool)):
        return str(cleaned)
    if not isinstance(cleaned, str):
        return 'null'

    plain = cleaned
    needs_q = needs_quotes(cleaned)

    if not needs_q and len(plain) <= max_width:
        return plain

    # Short: quote it
    if len(cleaned) <= max_width:
        escaped = cleaned.replace("'", "''")
        return f"'{escaped}'"
    else:
        # Long: wrap to multi-line
        wrapped = textwrap.wrap(cleaned, width=max_width)
        return '\n'.join(wrapped)

def dump_yaml(data: dict, indent: int = 0) -> str:
    lines = []
    space = "  " * indent
    order = ["id", "term", "version", "authors", "discussion", "categories", "tags",
             "definition", "history", "synonyms", "relationships",
             "prompt_examples", "examples", "agent_execution", "search_boost"]

    for key in order:
        if key not in data:
            continue
        value = data[key]
        if value is None or value == [] or value == {}:
            continue

        if isinstance(value, list):
            lines.append(f"{space}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{space}  -")
                    for subk, subv in item.items():
                        if subv not in (None, "", []):
                            sub_val_str = yaml_scalar(subv)
                            if '\n' in sub_val_str:
                                lines.append(f"{space}    {subk}: |")
                                for line in sub_val_str.splitlines():
                                    lines.append(f"{space}      {line}")
                            else:
                                scalar_line = f"{space}    {subk}: {sub_val_str}"
                                lines.append(scalar_line.rstrip())
                else:
                    item_str = yaml_scalar(item)
                    if '\n' in item_str:
                        lines.append(f"{space}  - |")
                        for line in item_str.splitlines():
                            lines.append(f"{space}    {line}")
                    else:
                        scalar_line = f"{space}  - {item_str}"
                        lines.append(scalar_line.rstrip())

        elif isinstance(value, dict):
            lines.append(f"{space}{key}:")
            for subk, subv in value.items():
                if isinstance(subv, list):
                    lines.append(f"{space}  {subk}:")
                    for action in subv:
                        action_str = yaml_scalar(action)
                        if '\n' in action_str:
                            lines.append(f"{space}    - |")
                            for line in action_str.splitlines():
                                lines.append(f"{space}      {line}")
                        else:
                            scalar_line = f"{space}    - {action_str}"
                            lines.append(scalar_line.rstrip())
                else:
                    sub_val_str = yaml_scalar(subv)
                    if '\n' in sub_val_str:
                        lines.append(f"{space}  {subk}: |")
                        for line in sub_val_str.splitlines():
                            lines.append(f"{space}    {line}")
                    else:
                        scalar_line = f"{space}  {subk}: {sub_val_str}"
                        lines.append(scalar_line.rstrip())

        else:
            # Top-level scalar
            val_str = yaml_scalar(value)
            if '\n' in val_str:
                lines.append(f"{space}{key}: |")
                for line in val_str.splitlines():
                    lines.append(f"{space}  {line}")
            else:
                scalar_line = f"{space}{key}: {val_str}"
                lines.append(scalar_line.rstrip())
    return "\n".join(lines)

def to_yaml(term: dict) -> None:
    canonical = term["canonical_term"]
    filename = term_to_filename(canonical)
    short_id = get_short_id(term.get("id", ""))

    meta = term.get("metadata", {})
    author_name = clean_quotes(meta.get("author", "Community Contributor"))
    author_first = author_name.split()[0].lower() if author_name else "community"
    org = AUTHOR_ORG.get(author_name, "")

    raw_date_added = meta.get("date_added", "2025-08-07")
    added_date = raw_date_added[:10] if raw_date_added else "2025-08-07"

    history = [
        {
            "date": added_date,
            "author": author_first,
            "reason": "Initial term addition to build registry"
        },
        {
            "date": added_date,
            "author": author_first,
            "reason": "Accepted into CAT-MIP registry"
        }
    ]

    agent_exec = term.get("agent_execution", {})
    interpretation_raw = clean_quotes(agent_exec.get("interpretation", ""))
    interpretation = interpretation_raw.rstrip(":").strip()  # remove trailing colon

    agent_actions_raw = agent_exec.get("actions", [])
    agent_actions = sorted(clean_quotes(a).lstrip("- ").strip() for a in agent_actions_raw if a)

    synonyms = sorted(clean_quotes(s) for s in term.get("synonyms", []) if s)
    relationships = sorted(clean_quotes(r) for r in term.get("relationships", []) if r)
    prompt_examples = sorted(clean_quotes(ex) for ex in term.get("prompt_examples", []) if ex)
    tags = sorted(set(["msp", "cat-mip", "core"] + [clean_quotes(t) for t in term.get("tags", []) if t]))

    data = {
        "id": short_id,
        "term": canonical,
        "version": meta.get("version", "1.0"),
        "authors": [
            {
                "name": author_name,
                "github": author_first,
                "org": org
            }
        ],
        "discussion": clean_quotes(meta.get("source_url", "")),
        "categories": meta.get("term_type", ["Core"]) if meta.get("term_type") else ["Core"],
        "tags": tags,
        "definition": clean_quotes(term["definition"]),
        "history": history,
        "synonyms": synonyms,
        "relationships": relationships,
        "prompt_examples": prompt_examples,
        "agent_execution": {
            "interpretation": interpretation,
            "actions": agent_actions
        } if interpretation or agent_actions else None
    }

    if "agent_execution" in data and data["agent_execution"] is None:
        del data["agent_execution"]

    content = dump_yaml(data) + "\n"

    path = STANDARDS / "accepted" / filename
    path.write_text(content, encoding="utf-8")
    print(f"Created → standards/accepted/{filename}")

def main():
    terms = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    for term in terms:
        to_yaml(term)
    print(f"\nAll {len(terms)} YAML files created!")

if __name__ == "__main__":
    main()
