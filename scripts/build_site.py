#!/usr/bin/env python3
"""
Generate MkDocs pages from standards/**/*.yaml

- Alphabetical folder indexes
- Auto-links terms in definitions, prompts, actions, reasons, etc.
- Copies exports (ASSETS, JSON, TTL)
- Cross-folder links (../draft/term.md)
- Longer terms first ("AI Agent" before "Agent")
- No self-links
- One method per Markdown section — crystal clear
- Skips fenced code blocks ``` and inline code `
- Slugified filenames (ai-agent.md)
- Smart Agent Execution rendering
"""

import pathlib
import yaml
import shutil
import re
from typing import Dict

ROOT = pathlib.Path(__file__).parent.parent
ASSETS = ROOT / "assets"
BUILD = ROOT / "build"
DOCS = BUILD / "docs"
IMAGES = DOCS / "images"
STANDARDS = ROOT / "standards"

# Clean and recreate docs
BUILD.mkdir(exist_ok=True)
shutil.rmtree(DOCS, ignore_errors=True)
DOCS.mkdir()
IMAGES.mkdir()

FOLDERS = ["accepted", "draft", "deprecated", "rejected"]

# ----------------------------------------------------------------------
# SLUGIFY
# ----------------------------------------------------------------------
def slugify(term: str) -> str:
    if not term:
        return "unknown"
    s = term.lower()
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')

# ----------------------------------------------------------------------
# LINKIFY ENGINE
# ----------------------------------------------------------------------
def _build_patterns(all_terms: Dict[str, dict], current_slug: str):
    patterns = []
    for norm, info in all_terms.items():
        if info["slug"] == current_slug:
            continue
        display = info["display"]
        escaped = re.escape(display)
        pat = re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)
        patterns.append((len(display), pat, info["slug"], info["folder"]))
    patterns.sort(key=lambda x: -x[0])
    return patterns

def _match_replace(prose: str, patterns: list, current_slug: str, current_folder: str) -> str:
    if not prose:
        return prose
    result = []
    pos = 0
    while pos < len(prose):
        matched = False
        for _length, pat, t_slug, t_folder in patterns:
            m = pat.match(prose, pos)
            if m:
                start, end = m.span()
                result.append(prose[pos:start])
                rel = f"../{t_folder}/{t_slug}.md" if t_folder != current_folder else f"{t_slug}.md"
                result.append(f"[{m.group(0)}]({rel})")
                pos = end
                matched = True
                break
        if not matched:
            result.append(prose[pos])
            pos += 1
    return "".join(result)

def linkify(text: str, all_terms: Dict[str, dict], current_slug: str, current_folder: str) -> str:
    if not text or not all_terms:
        return text

    patterns = _build_patterns(all_terms, current_slug)

    def linkify_prose(prose: str) -> str:
        if not prose:
            return prose
        res = []
        pos = 0
        while pos < len(prose):
            code_start = prose.find("`", pos)
            if code_start == -1:
                res.append(_match_replace(prose[pos:], patterns, current_slug, current_folder))
                break
            res.append(_match_replace(prose[pos:code_start], patterns, current_slug, current_folder))
            code_end = prose.find("`", code_start + 1)
            if code_end == -1:
                res.append(prose[code_start:])
                break
            res.append(prose[code_start:code_end + 1])
            pos = code_end + 1
        return "".join(res)

    result = []
    pos = 0
    while pos < len(text):
        fence_start = text.find("```", pos)
        if fence_start == -1:
            result.append(linkify_prose(text[pos:]))
            break
        result.append(linkify_prose(text[pos:fence_start]))
        fence_end = text.find("```", fence_start + 3)
        if fence_end == -1:
            result.append(text[fence_start:])
            break
        result.append(text[fence_start:fence_end + 3])
        pos = fence_end + 3
    return "".join(result)

# ----------------------------------------------------------------------
# SECTION METHODS
# ----------------------------------------------------------------------
def section_authors(meta):
    if not meta.get("authors"):
        return ""
    md = "authors:\n"
    for author in meta["authors"]:
        name = author.get("name", "")
        github = author.get("github", "")
        org = author.get("org", "")
        md += f"  - name: {name}\n"
        if github:
            md += f"    github: {github}\n"
        if org:
            md += f"    org: {org}\n"
    return md

def section_agent_execution(meta, linkify):
    agent = meta.get("agent_execution", {})
    interp_raw = agent.get("interpretation", "").rstrip(":").strip()
    interp = linkify(interp_raw) + (":" if interp_raw else "")

    actions = agent.get("actions", [])

    if not agent:
        return "## Agent Execution\n!!! warning\n\n    No execution defined\n\n"

    md = "## Agent Execution\n"
    if interp:
        md += f"{interp}\n\n"
    if actions:
        for a in actions:
            a = a.lstrip("- ").strip()
            md += f"- {linkify(a)}\n"
        md += "\n"
    elif not interp:
        md += "!!! info\n\n    No actions defined\n\n"
    return md

def section_banner(meta: dict, folder: str) -> str:
    """Folder = source of truth. Date/author only when reason starts with 'Status –'."""
    status_map = {
        "accepted":    ("success",  "Accepted"),
        "draft":       ("warning",  "Draft"),
        "deprecated":  ("failure",  "Deprecated"),
        "rejected":    ("note",     "Rejected"),
    }
    badge_type, badge_name = status_map.get(folder, ("note", "Unknown"))

    history = meta.get("history") or []
    parts = [badge_name]

    # Draft → always show creation date/author
    if folder == "draft" and history:
        first = history[0]
        date = first.get("date")
        author = first.get("author")
        if date:
            parts.append(date)
        if author:
            parts.append(f"by {author}")

    else:
        # Look for exact "Accepted –", "Deprecated –", "Rejected –" prefix
        prefix = f"{badge_name} –"
        for entry in reversed(history):
            reason = entry.get("reason", "")
            if reason.startswith(prefix):
                date = entry.get("date")
                author = entry.get("author")
                if date:
                    parts.append(date)
                if author:
                    parts.append(f"by {author}")
                break
        # No match → just the status name (clean!)

    return f"!!! {badge_type} \"{ ' • '.join(parts) }\"\n\n"

def section_definition(meta, linkify):
    raw = meta.get("definition", "").strip()
    if not raw:
        return ""
    return f"## Definition\n\n{linkify(raw)}\n\n"

def section_history(meta, linkify):
    history = meta.get("history")
    if not history:
        return ""
    md = "## History\n"
    md += "| Date       | Author   | Reason                          |\n"
    md += "| :--------- | :------- | :------------------------------ |\n"
    for h in history:
        reason = linkify(h.get("reason", ""))
        md += f"| {h.get('date', '')} | {h.get('author', '')} | {reason} |\n"
    return md + "\n"

def section_prompt_examples(meta, linkify):
    examples = meta.get("prompt_examples")
    if not examples:
        return ""
    md = "## Prompt Examples\n"
    for s in examples:
        md += f"- {linkify(s)}\n"
    md += "\n"
    return md

def section_relationships(meta, linkify):
    rels = meta.get("relationships")
    if not rels:
        return ""
    md = "## Relationships\n"
    for s in rels:
        md += f"- {linkify(s)}\n"
    md += "\n"
    return md

def section_synonyms(meta, linkify):
    syns = meta.get("synonyms")
    if not syns:
        return ""
    md = "## Synonyms\n"
    for s in syns:
        md += f"- {linkify(s)}\n"
    md += "\n"
    return md

def section_tags(meta):
    if not meta.get("tags"):
        return ""
    md = "tags:\n"
    for t in meta["tags"]:
        md += f"  - {t}\n"
    return md

# ----------------------------------------------------------------------
# GENERATE SINGLE PAGE
# ----------------------------------------------------------------------
def generate_term_page(meta: dict, slug: str, folder: str, all_terms: Dict[str, dict]):
    term = meta.get("term", "Unknown")
    term_id = meta.get("id", "DRAFT")

    def linkify(text):
        return globals()["linkify"](text, all_terms, slug, folder)

    md = '---\n'
    md += f'title: {term}\n'
    md += f'search_boost: 2.0\n'

    if meta.get("history"):
        first_date = meta["history"][0].get("date")
        if first_date:
            md += f'date: {first_date}\n'
        latest_date = meta["history"][-1].get("date")
        if latest_date and latest_date != first_date:
            md += f'updated: {latest_date}\n'

    md += section_authors(meta)
    md += section_tags(meta)
    md += '---\n\n'

    md += f"# {term} ({term_id})\n\n"
    md += section_banner(meta, folder)
    md += section_definition(meta, linkify)
    md += section_prompt_examples(meta, linkify)
    md += section_agent_execution(meta, linkify)
    md += section_synonyms(meta, linkify)
    md += section_relationships(meta, linkify)
    md += section_history(meta, linkify)

    out_dir = DOCS / folder
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{slug}.md"
    out_path.write_text(md)
    print(f"Generated → {out_path}")

# ----------------------------------------------------------------------
# FOLDER INDEX PAGES + MAIN
# ----------------------------------------------------------------------
def generate_folder_indexes(folder_terms):
    for folder, items in folder_terms.items():
        items_sorted = sorted(items, key=lambda x: x[0].lower())
        index_path = DOCS / folder / "index.md"
        title_map = {
            "accepted": "Accepted Terms",
            "draft": "Draft Terms",
            "deprecated": "Deprecated Terms",
            "rejected": "Rejected Terms"
        }
        title = title_map[folder]

        index_md = '---\nsearch:\n  exclude: true\n  boost: 0\n---\n'
        index_md += f"# {title}\n\nAll {folder} terms in the CAT-MIP registry.\n\n"
        if items_sorted:
            index_md += "## Terms\n\n"
            for term, term_id, slug in items_sorted:
                index_md += f"- [{term} ({term_id})]({slug}.md)\n"
        else:
            index_md += "_No terms yet._\n"

        index_path.parent.mkdir(exist_ok=True)
        index_path.write_text(index_md)

def main():
    for folder in FOLDERS:
        (DOCS / folder).mkdir(exist_ok=True)

    all_terms = {}
    folder_terms = {f: [] for f in FOLDERS}

    # Only YAML files inside the four status folders — ignores root completely
    for yaml_path in STANDARDS.glob("*/*.yaml"):
        folder = yaml_path.parent.name
        if folder not in FOLDERS:
            continue
        meta = yaml.safe_load(yaml_path.read_text())
        term = meta.get("term", yaml_path.stem.replace("-", " ").title())
        term_id = meta.get("id", "DRAFT")
        slug = slugify(term)
        norm = term.lower()

        if norm in all_terms:
            print(f"WARNING: Duplicate term (ignoring case): {term}")
            slug += "-dup"

        all_terms[norm] = {
            "display": term,
            "slug": slug,
            "folder": folder,
            "id": term_id,
        }
        folder_terms[folder].append((term, term_id, slug))

    generate_folder_indexes(folder_terms)

    # Second pass — same glob, same safety
    for yaml_path in STANDARDS.glob("*/*.yaml"):
        folder = yaml_path.parent.name
        if folder not in FOLDERS:
            continue
        meta = yaml.safe_load(yaml_path.read_text())
        term = meta.get("term", yaml_path.stem.replace("-", " ").title())
        norm = term.lower()
        if norm not in all_terms:
            continue
        info = all_terms[norm]
        generate_term_page(meta, info["slug"], folder, all_terms)

    # Root index
    standards_index = ASSETS / "docs/index.md"
    target = DOCS / "index.md"
    if standards_index.exists():
        target.write_text(standards_index.read_text())
    else:
        target.write_text("---\nsearch:\n  exclude: true\n---\n\n# CAT-MIP Terminology Registry\n\nWelcome to the official registry.\n")

    # Copy extra assets
    extra_src = ASSETS / "docs"
    if extra_src.exists() and extra_src.is_dir():
        for item in extra_src.iterdir():
            if item.name == "index.md":
                continue
            dest = DOCS / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

    logo = ASSETS / "images/catmip-150x150.png"
    if logo.exists():
        shutil.copy(logo, IMAGES / "catmip-150x150.png")

    print("\nSite generated")

if __name__ == "__main__":
    main()
