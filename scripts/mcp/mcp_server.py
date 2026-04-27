"""
mcp-server.py

Simple MCP server that reads in /build/cat-mip-flat.json to build a
RAG store in a a persistent ChromaDB instance.

Server has two function:
    chroma_peek: returns the top 5 items in the collection, primarily to show what the
       structure looks like
    chroma_fetch: accepts a text string from the caller and retrieves the top matches


The server can run as stdio (default) for simple, local installations.

It can also run over HTTP via SSE, but is not production ready in the sense
it that there is no authentication and no protection against malicious calls.
These can be added as per your security guidelines but some assembly is required.
It is strongly recommended that code as is only be run locally or even a sandboxed
instance.

Usage:
    python scripts/mcp/mcp_server.py         #stdio
    python scripts/mcp/mcp_server.py --http  #HTTP on port 8000

This dependent on cat-mip-flat.json so make sure you have run 
build_flat_json.py prior to running this.

This will also create an on-disc copy of the ChromaDB store if one does not already
exist. Simply delete the contents of scripts/mcp/cat-mip-chroma to force a rebuild, 
for example when a new verion of CAT-MIP is available.

Ignore the following warning, it is normal:
UNEXPECTED:   can be ignored when loading from different task/architecture

"""

import pathlib 
import argparse
import json
import numpy as np

import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings
from sentence_transformers import SentenceTransformer
from fastmcp import FastMCP


ROOT = pathlib.Path(__file__).parent.parent.parent
BUILD = ROOT / "build"
JSON_FILE = BUILD / "cat-mip-flat.json"


COLLECTION = "cat-mip"
CHROMA_DIR = pathlib.Path(__file__).parent / "cat-mip-chroma"
MODEL_NAME = "all-MiniLM-L6-v2"

# ----------------------------------------------------------------------
# SET UP EMBEDDER
# ----------------------------------------------------------------------

class Embedder(EmbeddingFunction):
    
    def __init__(self) -> None:
        print(f".   Loading model: {MODEL_NAME}")
        self._model = SentenceTransformer(MODEL_NAME)

    def __call__(self, input: Documents) -> Embeddings:
        return self._model.encode(
            list(input), normalize_embeddings=True
        ).tolist()
    
    def encode_one(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()
    

# ----------------------------------------------------------------------
# LOAD CAT-MIP INTO CHROMA
# ----------------------------------------------------------------------
def build_index(embedder: Embedder) -> chromadb.Collection:
    """
    Read the cat-mip-flat.json file from the build directory and load into
    ChromaDB collection.  Called at startup. 

    To force a rebuild, delete scripts/mcp/cat-mip-chroma/ and restart the server.
    """


    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    existing = any(c.name == COLLECTION for c in client.list_collections())

    if existing:
        collection = client.get_collection(COLLECTION, embedding_function=embedder)
        print(f"  Opened existing index — {collection.count()} docs")
        return collection

    if not JSON_FILE.exists():
        raise FileNotFoundError(
            f"Source file {JSON_FILE} not found\n"
            f"Run scripts/build_flat_json.py first"
        )
    
    terms = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    print(f"   Ingesting {len(terms)} from {JSON_FILE.name}")

   
    collection = client.get_or_create_collection(
        COLLECTION,
        embedding_function= embedder,
        metadata= {"hnsw:space": "cosine"},
    )

    collection.upsert(
        ids = [str(i) for i, _ in enumerate(terms)],
        documents= [t["body"] for t in terms],
        metadatas= [{"term": t["term"], "id": i} for i, t in enumerate(terms)],
    )

    print(f".   Index ready - {collection.count()} docs")

    return collection

# ----------------------------------------------------------------------
# MCP SERVER
# ----------------------------------------------------------------------

mcp = FastMCP(
    "cat-mip",
    instructions=(
        "CAT-MIP is a canonical terminology registry for MSP and IT environments. "
        "Use the chroma_fetch tool to resolve ambiguous vocabulary before acting on "
        "a prompt. Always disambiguate terms like 'account', 'device', 'resource', "
        "or 'organization' when their precise meaning is unclear."
    ),
)

# Populated in main() before mcp.run()
_embedder:   Embedder | None            = None
_collection: chromadb.Collection | None = None


@mcp.tool()
def chroma_peek(limit: int = 5) -> str:

    """
    Preview the first x documents in the CAT-MIP ChromaDb collection
    Limits each result to 200 characters

    Args:
        limit: sets number of documents retrieved, max = 10
    """
    
    limit = max(1, min(limit,10))
    results = _collection.peek(limit=limit)

    items = []
    for id_, meta, doc in zip(
        results["ids"],
        results["metadatas"],
        results["documents"],
    ):
        items.append({
            "id": id_,
            "term": meta["term"],
            "body": doc[:200] + ("..." if len(doc) > 200 else ""),
        })

    return json.dumps(
        {"total_docs": _collection.count(), "peek": items},
        indent=2,
        ensure_ascii=False
    )


@mcp.tool()
def chroma_fetch(text: str, n_results: int = 5) -> str:
    """
    Encode incoming text with all-MiniLM-L6-v2 and return the top-matching
    CAT-MIP canonical terms.
 
    Use this whenever a prompt contains MSP/IT vocabulary that could be
    interpreted in more than one way — e.g. 'account', 'agent', 'device',
    'client', 'resource', 'organization'. Returns canonical term, relevance
    score (0-1), and full body text so the caller can resolve ambiguity
    before acting.
 
    Args:
        text:      Text to disambiguate — word, phrase, or full sentence.
        n_results: Candidates to return. Default 5, max 10.
    """  

    n_results =  max(1, min(n_results, 10))
    query_vec = _embedder.encode_one(text)

    results = _collection.query(
        query_embeddings=np.array([query_vec], dtype=np.float32),
        n_results=n_results,
        include=["metadatas", "distances", "documents"],
     )

    hits = []
    for meta, dist, body in zip(
        results["metadatas"][0],
        results["distances"][0],
        results["documents"][0],      
     ):
         hits.append({
             "term": meta["term"],
             "relevance_score": round(1 - dist, 4),
             "body": body,
         })

    return json.dumps(hits, indent=2, ensure_ascii=False)


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main() -> None:
    global _embedder, _collection

    parser = argparse.ArgumentParser(description="CAT-MIP server")
    parser.add_argument("--http", action="store_true",
                        help="Run as HTTP/SSE server instead of stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    print("CAT-MIP server starting...")

    _embedder = Embedder()
    _collection = build_index(_embedder)

    if args.http:
        print(f"Transport: HTTP/SSE on {args.host}:{args.port}")
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        print("Transport: stdio (Claude Desktop mode)")
        mcp.run(transport="stdio")

  
if __name__ == "__main__":
    main()

