#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle, ListStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    ListFlowable, ListItem, PageBreak
)
from reportlab.pdfbase.pdfmetrics import stringWidth

# ---------- Styles ----------
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="CoverTitle", parent=styles["Title"], fontSize=22, alignment=1,  # 0=left, 1=center, 2=right, 4=justify
    spaceAfter=20
))
styles.add(ParagraphStyle(
    name="CoverDate", parent=styles["Normal"], fontSize=12, alignment=1, textColor=colors.grey
))
styles.add(ParagraphStyle(
    name="TitleTerm", parent=styles["Title"], fontSize=14, spaceAfter=6
))
styles.add(ParagraphStyle(
    name="H2", parent=styles["Heading2"], fontSize=9, spaceBefore=6, spaceAfter=0
))
styles.add(ParagraphStyle(
    name="Meta", parent=styles["Normal"], fontSize=9, textColor=colors.grey
))
styles.add(ParagraphStyle(
    name="Body", parent=styles["Normal"], fontSize=9, leading=14
))
styles.add(ParagraphStyle(
    name="Key", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#333")
))
styles.add(ParagraphStyle(
    name="Mono", parent=styles["Normal"], fontSize=9, leading=12
))
bullet_style = ListStyle("Bullets")
bullet_style.leftIndent = 18
bullet_style.bulletIndent = 9
bullet_style.bulletFontSize = 9
bullet_style.bulletColor = colors.HexColor("#333")
num_style = ListStyle("Numbers")
num_style.leftIndent = 18
num_style.bulletIndent = 9

PAGE_W, PAGE_H = LETTER
MARGIN = 0.5 * inch

# ---------- Helpers ----------

def build_cover_story():
    story = []
    today = datetime.utcnow().strftime("%B %d, %Y")
    title = "Consortium for AI Terminology for MSPs & IT Pros (CAT-MIP)"
    # Spacer pushes content down ~half the page
    story.append(Spacer(1, PAGE_H/3))
    story.append(Paragraph(title, styles["CoverTitle"]))
    story.append(Spacer(1, 0.25*inch))
    story.append(Paragraph(f"Generated on {today}", styles["CoverDate"]))
    story.append(PageBreak())
    return story

def _p(text, style="Body"):
    if text is None:
        text = ""
    # Basic sanitization for PDF paragraphs
    text = str(text).replace("\n", "<br/>")
    return Paragraph(text, styles[style])

def _kv_table(kv_pairs):
    if not kv_pairs:
        return None
    data = [[Paragraph(f"<b>{k}</b>", styles["Key"]), _p(v, "Body")] for k, v in kv_pairs]
    tbl = Table(data, colWidths=[1.6*inch, None])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.whitesmoke, colors.Color(1,1,1)]),
        ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
    ]))
    return tbl

def _list_flow(items, numbered=False):
    if not items:
        return None
    style = num_style if numbered else bullet_style
    # Coerce items to strings
    flow = ListFlowable(
        [ListItem(_p(str(x))) for x in items],
        bulletType="1" if numbered else "bullet"
    )
    flow._listStyle = style
    return flow

def _slugify(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s))[:150]

def _page_footer(canvas, doc):
    canvas.saveState()
    footer = f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')}"
    w = stringWidth(footer, "Helvetica", 8)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(MARGIN, 0.5*inch, footer)
    page_num = f"Page {doc.page}"
    canvas.drawString(PAGE_W - MARGIN - stringWidth(page_num, "Helvetica", 8), 0.5*inch, page_num)
    canvas.restoreState()

# ---------- Render a single term ----------
def build_term_story(item):
    story = []
    # Title line: canonical_term or id
    title = item.get("canonical_term") or item.get("name") or item.get("title") or item.get("id") or "Term"
    story.append(_p(title, "TitleTerm"))

    # Meta row
    meta_bits = []
    for key in ["id", "version", "registry", "date_added"]:
        if item.get(key):
            meta_bits.append(f"<b>{key}</b>: {item[key]}")
    if meta_bits:
        story.append(_p(" | ".join(meta_bits), "Meta"))
        story.append(Spacer(1, 6))

    # Definition
    if item.get("definition"):
        story.append(_p("Definition", "H2"))
        story.append(_p(item["definition"]))
        story.append(Spacer(1, 6))

    # Synonyms
    syns = item.get("synonyms") or []
    if isinstance(syns, list) and syns:
        story.append(_p("Synonyms", "H2"))
        flow = _list_flow(syns, numbered=False)
        if flow: story.append(flow)
        story.append(Spacer(1, 6))

    # Relationships
    rels = item.get("relationships") or []
    if isinstance(rels, list) and rels:
        story.append(_p("Relationships", "H2"))
        flow = _list_flow(rels, numbered=False)
        if flow: story.append(flow)
        story.append(Spacer(1, 6))

    # Prompt examples
    ex = item.get("prompt_examples") or []
    if isinstance(ex, list) and ex:
        story.append(_p("Prompt examples", "H2"))
        flow = _list_flow(ex, numbered=False)
        if flow: story.append(flow)
        story.append(Spacer(1, 6))

    # Agent execution
    agent = item.get("agent_execution") or {}
    if isinstance(agent, dict) and agent:
        story.append(_p("Agent execution", "H2"))
        interp = agent.get("interpretation")
        if interp:
            story.append(_p("<b>Interpretation</b>", "Body"))
            story.append(_p(interp))
            story.append(Spacer(1, 4))
        actions = agent.get("actions")
        if isinstance(actions, list) and actions:
            story.append(_p("<b>Actions</b>", "Body"))
            flow = _list_flow(actions, numbered=False)
            if flow: story.append(flow)
            story.append(Spacer(1, 6))

    # Metadata section
    meta = item.get("metadata") or {}
    if isinstance(meta, dict) and meta:
        story.append(_p("Metadata", "H2"))
        kvs = []
        for k in ["author", "source_url"]:
            if meta.get(k):
                kvs.append((k, meta[k]))
        others = [(k, v) for k, v in meta.items() if k not in {"author", "source_url"}]
        kvs.extend(others)
        tbl = _kv_table(kvs)
        if tbl: story.append(tbl)
        story.append(Spacer(1, 6))

    # Any remaining fields not handled above
    used = {"id","canonical_term","name","title","definition","synonyms","relationships",
            "prompt_examples","agent_execution","metadata","version","date_added","registry"}
    leftover = [(k, item[k]) for k in item.keys() if k not in used]
    if leftover:
        story.append(_p("Other fields", "H2"))
        # Coerce values to strings
        kvs = [(k, json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v) for k,v in leftover]
        tbl = _kv_table(kvs)
        if tbl: story.append(tbl)

    return story

# ---------- Main convert paths ----------
def render_to_pdf(data, out_path, split_items=False):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if split_items and isinstance(data, list):
        made = []
        for idx, item in enumerate(data):
            safe = None
            if isinstance(item, dict):
                for key in ["id", "canonical_term", "name", "title"]:
                    if item.get(key):
                        safe = _slugify(item[key])
                        break
            if not safe:
                safe = f"item_{idx:04d}"
            fname = f"{out_path.stem}-{safe}.pdf"
            doc = SimpleDocTemplate(str(out_path.parent / fname),
                                    pagesize=LETTER, leftMargin=MARGIN, rightMargin=MARGIN,
                                    topMargin=MARGIN, bottomMargin=MARGIN)
            story = build_term_story(item if isinstance(item, dict) else {"value": item})
            doc.build(story, onLaterPages=_page_footer, onFirstPage=_page_footer)
            made.append(str(out_path.parent / fname))
        return made
    else:
        # Single PDF containing all content with page breaks between items when list
        doc = SimpleDocTemplate(str(out_path),
                                pagesize=LETTER, leftMargin=MARGIN, rightMargin=MARGIN,
                                topMargin=MARGIN, bottomMargin=MARGIN)
        story = []
         # Add cover page first
        story.extend(build_cover_story())

        # Then add terms
        if isinstance(data, list):
            for i, item in enumerate(data):
                story.extend(build_term_story(item if isinstance(item, dict) else {"value": item}))
                if i < len(data) - 1:
                    story.append(PageBreak())
        elif isinstance(data, dict):
            story.extend(build_term_story(data))
        else:
            story.append(_p("Unsupported top-level JSON type", "Body"))
        doc.build(story, onLaterPages=_page_footer, onFirstPage=_page_footer)
        return [str(out_path)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="build/cat-mip.json", help="Path to JSON input")
    ap.add_argument("--outdir", default="build/pdfs", help="Output directory")
    ap.add_argument("--split-items", action="store_true", help="One PDF per item if input is a list")
    ap.add_argument("--outfile", default=None, help="Optional explicit output filename")
    args = ap.parse_args()

    data = json.load(open(args.input, "r", encoding="utf-8"))
    out_dir = Path(args.outdir); out_dir.mkdir(parents=True, exist_ok=True)
    out_file = Path(args.outfile) if args.outfile else out_dir / (Path(args.input).stem + ".pdf")
    made = render_to_pdf(data, out_file, split_items=args.split_items)
    for p in made:
        print("Created:", p)

if __name__ == "__main__":
    main()
