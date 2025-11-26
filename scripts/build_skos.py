#!/usr/bin/env python3
"""
Build cat-mip-skos.ttl from standards/accepted/*.yaml
- SKOS ConceptScheme with all accepted terms
- Alphabetical order
- skos:prefLabel, altLabel, definition
- skos:related for parsed relationships
- dcterms:issued from first history date
- Output to build/cat-mip-skos.ttl
"""

import pathlib
import yaml
import re
from rdflib import Graph, Literal, RDF, RDFS, SKOS, Namespace, URIRef
from rdflib.namespace import DCTERMS

ROOT = pathlib.Path(__file__).parent.parent
STANDARDS = ROOT / "standards/accepted"
BUILD = ROOT / "build"
BUILD.mkdir(exist_ok=True)
OUTPUT = BUILD / "cat-mip-skos.ttl"

# Namespaces
CATMIP = Namespace("https://cat-mip.org/terms/")
SKOSNS = Namespace("http://www.w3.org/2004/02/skos/core#")

g = Graph()
g.bind("skos", SKOS)
g.bind("dcterms", DCTERMS)
g.bind("catmip", CATMIP)

# Concept Scheme
scheme = CATMIP[""]
g.add((scheme, RDF.type, SKOS.ConceptScheme))
g.add((scheme, SKOS.prefLabel, Literal("CAT-MIP Terminology Registry", lang="en")))
g.add((scheme, DCTERMS.creator, Literal("CAT-MIP Community")))
g.add((scheme, DCTERMS.issued, Literal("2025-09-19")))

# Load all terms for linking
term_to_info = {}  # term_lower → (slug, meta)
for yaml_path in STANDARDS.glob("*.yaml"):
    meta = yaml.safe_load(yaml_path.read_text())
    term = meta.get("term", "")
    if term:
        term_lower = term.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', term_lower).strip('-')
        term_to_info[term_lower] = (slug, meta)

# Sort alphabetically
sorted_terms = sorted(term_to_info.items(), key=lambda x: x[0])

# Create concepts
for term_lower, (slug, meta) in sorted_terms:
    concept_uri = CATMIP[slug]

    g.add((concept_uri, RDF.type, SKOS.Concept))
    g.add((concept_uri, SKOS.inScheme, scheme))
    g.add((concept_uri, SKOS.prefLabel, Literal(meta["term"], lang="en")))

    if meta.get("definition"):
        g.add((concept_uri, SKOS.definition, Literal(meta["definition"], lang="en")))

    for syn in meta.get("synonyms", []):
        g.add((concept_uri, SKOS.altLabel, Literal(syn, lang="en")))

    # Issued date from first history
    if meta.get("history"):
        first_date = meta["history"][0].get("date")
        if first_date:
            g.add((concept_uri, DCTERMS.issued, Literal(first_date)))

    # Relationships — parse "A relatesTo B" and link if B is known
    for rel in meta.get("relationships", []):
        # Find other terms mentioned
        words = re.findall(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b', rel)
        for word in words:
            word_lower = word.lower()
            if word_lower in term_to_info and word_lower != term_lower:
                target_slug, _ = term_to_info[word_lower]
                target_uri = CATMIP[target_slug]
                g.add((concept_uri, SKOS.related, target_uri))

# Write Turtle
OUTPUT.write_text(g.serialize(format="turtle"), encoding="utf-8")

print(f"Exported {len(sorted_terms)} terms → {OUTPUT}")
