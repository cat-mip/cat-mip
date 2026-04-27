"""
test_mcp.py
───────────
Test suite for the CAT-MIP MCP server and client.

Three layers:
  Unit tests        — import server module, call tools directly, no HTTP needed
  Content tests     — verify returned body text contains expected concepts
  Integration tests — start HTTP server in background thread, use CatMipClient
                      with the real session handshake over localhost

Run all tests:
    python scripts/mcp/test_mcp.py

Unit tests only (no server required):
    python scripts/mcp/test_mcp.py --unit-only

Integration tests only (requires server to be startable):
    python scripts/mcp/test_mcp.py --integration-only

Custom port (if 8765 is in use):
    python scripts/mcp/test_mcp.py --port 9000
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path


# ── Test harness ──────────────────────────────────────────────────────────────

passed = failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        print(f"  ✓  {name}")
        passed += 1
    else:
        print(f"  ✗  {name}" + (f"\n       {detail}" if detail else ""))
        failed += 1


def section(title: str) -> None:
    print(f"\n── {title} {'─' * max(0, 55 - len(title))}")


# ── Module loader ─────────────────────────────────────────────────────────────

def load_module(name: str, filename: str):
    here = Path(__file__).parent
    path = here / filename
    if not path.exists():
        print(f"FATAL: {path} not found")
        sys.exit(1)
    spec   = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ══════════════════════════════════════════════════════════════════════════════
# 1. Unit tests — call server tools directly, no HTTP
# ══════════════════════════════════════════════════════════════════════════════

def run_unit_tests(srv) -> None:
    section("Unit tests  (direct function calls)")

    def fetch(text: str, n: int = 5) -> list[dict]:
        return json.loads(srv.chroma_fetch(text, n))

    def peek(limit: int = 5) -> dict:
        return json.loads(srv.chroma_peek(limit))

    # T01 — chroma_fetch returns a list
    try:
        r = fetch("backup", 3)
        check("T01: chroma_fetch returns valid JSON list", isinstance(r, list))
    except Exception as e:
        check("T01: chroma_fetch returns valid JSON list", False, str(e))
        return

    # T02 — n_results respected
    for n in (1, 3, 5):
        r = fetch("network device", n)
        check(f"T02: n_results={n} returns exactly {n} results",
              len(r) == n, f"got {len(r)}")

    # T03 — required keys present
    r = fetch("patch management")
    required = {"term", "relevance_score", "body"}
    missing  = required - set(r[0].keys()) if r else required
    check("T03: each result has term, relevance_score, body",
          not missing, f"missing: {missing}")

    # T04 — scores are floats in [0, 1]
    r = fetch("wireless access point")
    ok = all(isinstance(h["relevance_score"], float)
             and 0.0 <= h["relevance_score"] <= 1.0 for h in r)
    check("T04: relevance scores are floats in [0, 1]", ok,
          f"scores: {[h['relevance_score'] for h in r]}")

    # T05 — scores are descending
    r     = fetch("software installation package", 5)
    scores = [h["relevance_score"] for h in r]
    check("T05: results sorted by descending relevance score",
          scores == sorted(scores, reverse=True), f"scores: {scores}")

    # T06 — exact term lookup
    r     = fetch("Backup", 5)
    terms = [h["term"] for h in r]
    check("T06: querying 'Backup' surfaces Backup in top 5",
          "Backup" in terms, f"got: {terms}")

    # T07 — ambiguous term
    r     = fetch("account", 5)
    terms = [h["term"] for h in r]
    check("T07: ambiguous term 'account' surfaces Account entry",
          "Account" in terms, f"got: {terms}")

    # T08 — semantic query
    r     = fetch("software component that monitors endpoints remotely", 5)
    terms = [h["term"] for h in r]
    check("T08: semantic query surfaces Agent",
          "Agent" in terms, f"got: {terms}")

    # T09 — acronym
    r     = fetch("WMI", 3)
    terms = [h["term"] for h in r]
    check("T09: acronym 'WMI' surfaces WMI entry",
          "WMI" in terms, f"got: {terms}")

    # T10 — n_results capped at 10
    r = fetch("device", 99)
    check("T10: n_results capped at 10", len(r) <= 10, f"got {len(r)}")

    # T11 — n_results floored at 1
    r = fetch("firewall", 0)
    check("T11: n_results=0 still returns at least 1 result",
          len(r) >= 1, f"got {len(r)}")

    # T12 — body is a non-empty string (full text, not truncated)
    r = fetch("tenant customer MSP")
    check("T12: body is a non-empty string for all results",
          all(isinstance(h["body"], str) and len(h["body"]) > 20 for h in r))

    # T13 — body is not truncated (no trailing ellipsis)
    r = fetch("backup restore policy")
    truncated = [h["term"] for h in r if h["body"].endswith("...")]
    check("T13: body fields are not truncated",
          not truncated, f"truncated: {truncated}")

    # T14 — chroma_peek returns valid structure
    try:
        p = peek(5)
        check("T14: chroma_peek returns dict with total_docs and peek",
              isinstance(p, dict) and "total_docs" in p and "peek" in p)
    except Exception as e:
        check("T14: chroma_peek returns valid structure", False, str(e))
        return

    # T15 — peek count matches limit
    for limit in (1, 3, 5):
        p = peek(limit)
        check(f"T15: peek limit={limit} returns {limit} items",
              len(p["peek"]) == limit, f"got {len(p['peek'])}")

    # T16 — peek items have required keys
    p       = peek(3)
    required = {"id", "term", "body"}
    missing  = required - set(p["peek"][0].keys()) if p["peek"] else required
    check("T16: each peek item has id, term, body",
          not missing, f"missing: {missing}")

    # T17 — total_docs matches collection count
    p = peek(1)
    check("T17: total_docs matches collection count",
          p["total_docs"] == srv._collection.count(),
          f"peek={p['total_docs']} collection={srv._collection.count()}")

    # T18 — financial term
    r     = fetch("monthly recurring subscription revenue", 3)
    terms = [h["term"] for h in r]
    check("T18: financial query surfaces MRR or ARR",
          "MRR" in terms or "ARR" in terms, f"got: {terms}")

    # T19 — network term
    r     = fetch("SNMP OID polling network device metrics", 5)
    terms = [h["term"] for h in r]
    check("T19: 'SNMP OID polling' surfaces SNMP and OID",
          "SNMP" in terms and "OID" in terms, f"got: {terms}")

    # Content validation
    run_content_tests(fetch)




# ══════════════════════════════════════════════════════════════════════════════
# 3. Content validation tests — verify returned body contains expected text
# ══════════════════════════════════════════════════════════════════════════════

# These tests check not just which term is returned, but whether the body
# content contains the expected concepts — confirming the index was built
# correctly and the right data is coming back.

CONTENT_TESTS = [
    {
        "id":       "C01",
        "query":    "how do I manage access to systems using a single login?",
        "expected_term": "SSO",
        "expected_in_body": [
            "Single Sign-On",
            "identity",
            "authentication",
        ],
        "description": "SSO body contains key authentication concepts",
    },
    {
        "id":       "C02",
        "query":    "what term should I use instead of account to refer to a managed customer?",
        "expected_term": "Tenant",
        "expected_in_body": [
            "MSP",
            "logically isolated",
            "Customer",
        ],
        "description": "Tenant body explains the customer/MSP relationship",
    },
    {
        "id":       "C03",
        "query":    "scheduled or event triggered copy of data used for disaster recovery",
        "expected_term": "Backup",
        "expected_in_body": [
            "restore",
            "data loss",
            "policy",
        ],
        "description": "Backup body contains restore and policy concepts",
    },
    {
        "id":       "C04",
        "query":    "known flaw in software that can be exploited by an attacker",
        "expected_term": "Vulnerability",
        "expected_in_body": [
            "CVE",
            "severity",
            "patch",
        ],
        "description": "Vulnerability body contains CVE, severity, and patch",
    },
]


def run_content_tests(fetch_fn) -> None:
    section("Content validation tests  (query → expected term + body text)")

    for tc in CONTENT_TESTS:
        print(f"\n  {tc['id']}: {tc['description']}")
        print(f"  Query    : {tc['query']!r}")

        try:
            results = fetch_fn(tc["query"], 5)
        except Exception as e:
            check(f"{tc['id']}: fetch succeeded", False, str(e))
            continue

        terms = [h["term"] for h in results]
        print(f"  Results  : {terms}")

        # Check the expected term appears in top 5
        term_found = tc["expected_term"] in terms
        check(f"{tc['id']}: '{tc['expected_term']}' in top 5 results", term_found,
              f"got: {terms}")

        # Find the matching result and check its body
        match = next((h for h in results if h["term"] == tc["expected_term"]), None)
        if match:
            body = match["body"].lower()
            print(f"  Score    : {match['relevance_score']}")
            for phrase in tc["expected_in_body"]:
                found = phrase.lower() in body
                check(
                    f"{tc['id']}: body contains {phrase!r}",
                    found,
                    f"not found in body for term '{tc['expected_term']}'",
                )
        else:
            for phrase in tc["expected_in_body"]:
                check(f"{tc['id']}: body contains {phrase!r}", False,
                      f"term '{tc['expected_term']}' not in results, cannot check body")

# ══════════════════════════════════════════════════════════════════════════════
# 2. Integration tests — real HTTP via CatMipClient
# ══════════════════════════════════════════════════════════════════════════════

def start_http_server(srv, port: int) -> None:
    def _run():
        try:
            srv.mcp.run(transport="http", host="127.0.0.1", port=port)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def run_integration_tests(srv, client_mod, port: int = 8765) -> None:
    section("Integration tests  (HTTP via CatMipClient)")

    print(f"  Starting HTTP server on port {port}...")
    start_http_server(srv, port)
    time.sleep(2)   # give uvicorn time to bind

    client = client_mod.CatMipClient(f"http://127.0.0.1:{port}")
    try:
        client.connect(timeout=12)
        check("I01: HTTP server starts and session handshake succeeds",
              client._session_id is not None,
              f"session_id={client._session_id}")
    except Exception as e:
        check("I01: HTTP server starts and session handshake succeeds",
              False, str(e))
        print("  Server did not start — skipping remaining integration tests")
        return

    # I02 — session ID is a non-empty string
    check("I02: session ID is a non-empty string",
          isinstance(client._session_id, str) and len(client._session_id) > 0,
          f"got: {client._session_id!r}")

    # I03 — chroma_fetch returns a list over HTTP
    try:
        r = client.fetch("backup", n_results=3)
        check("I03: chroma_fetch returns a list over HTTP",
              isinstance(r, list) and len(r) == 3)
    except Exception as e:
        check("I03: chroma_fetch returns a list over HTTP", False, str(e))
        return

    # I04 — n_results respected over HTTP
    r = client.fetch("agent monitoring", n_results=4)
    check("I04: n_results=4 returns 4 results over HTTP",
          len(r) == 4, f"got {len(r)}")

    # I05 — required keys present over HTTP
    r       = client.fetch("firewall", n_results=3)
    required = {"term", "relevance_score", "body"}
    missing  = required - set(r[0].keys()) if r else required
    check("I05: all results contain term, relevance_score, body",
          not missing, f"missing: {missing}")

    # I06 — scores valid over HTTP
    r = client.fetch("patch update", n_results=3)
    check("I06: relevance scores valid over HTTP",
          all(0.0 <= h.get("relevance_score", -1) <= 1.0 for h in r),
          f"scores: {[h.get('relevance_score') for h in r]}")

    # I07 — body is full text, not truncated
    r         = client.fetch("backup policy agent monitoring", n_results=3)
    truncated = [h["term"] for h in r if h["body"].endswith("...")]
    check("I07: body fields are full text, not truncated over HTTP",
          not truncated, f"truncated: {truncated}")

    # I08 — semantic query over HTTP
    r     = client.fetch("rules that govern how devices should behave", n_results=5)
    terms = [h["term"] for h in r]
    check("I08: semantic query 'rules that govern devices' surfaces Policy",
          "Policy" in terms, f"got: {terms}")

    # I09 — ambiguous term over HTTP
    r     = client.fetch("organization", n_results=5)
    terms = [h["term"] for h in r]
    check("I09: 'organization' surfaces Organization over HTTP",
          "Organization" in terms, f"got: {terms}")

    # I10 — repeated calls stable (same top result)
    r1 = client.fetch("SSH remote access", n_results=1)
    r2 = client.fetch("SSH remote access", n_results=1)
    check("I10: repeated identical queries return same top result",
          r1[0]["term"] == r2[0]["term"],
          f"r1={r1[0]['term']}  r2={r2[0]['term']}")

    # I11 — chroma_peek over HTTP
    try:
        p = client.peek(limit=3)
        check("I11: chroma_peek returns valid structure over HTTP",
              isinstance(p, dict) and "total_docs" in p and "peek" in p)
    except Exception as e:
        check("I11: chroma_peek returns valid structure over HTTP", False, str(e))
        return

    # I12 — peek count over HTTP
    p = client.peek(limit=4)
    check("I12: peek limit=4 returns 4 items over HTTP",
          len(p["peek"]) == 4, f"got {len(p['peek'])}")

    # I13 — total_docs positive integer over HTTP
    p = client.peek(limit=1)
    check("I13: total_docs is a positive integer over HTTP",
          isinstance(p["total_docs"], int) and p["total_docs"] > 0,
          f"got: {p['total_docs']}")

    # I14 — financial term over HTTP
    r     = client.fetch("monthly recurring subscription revenue", n_results=3)
    terms = [h["term"] for h in r]
    check("I14: financial query surfaces MRR or ARR over HTTP",
          "MRR" in terms or "ARR" in terms, f"got: {terms}")

    # Content validation over HTTP
    run_content_tests(lambda text, n: client.fetch(text, n_results=n))

    # I15 — second client with same server (session independence)
    client2 = client_mod.CatMipClient(f"http://127.0.0.1:{port}")
    try:
        client2.connect(timeout=5)
        check("I15: second client gets its own independent session ID",
              client2._session_id != client._session_id,
              f"c1={client._session_id}  c2={client2._session_id}")
    except Exception as e:
        check("I15: second client connects independently", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# 3. Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="CAT-MIP MCP test suite")
    parser.add_argument("--unit-only",        action="store_true")
    parser.add_argument("--integration-only", action="store_true")
    parser.add_argument("--port", type=int, default=8765,
                        help="Port for integration HTTP server (default 8765)")
    args = parser.parse_args()

    print("\n══ CAT-MIP MCP Test Suite ══════════════════════════════════════\n")
    print("Loading server module (builds model + index)...")
    srv = load_module("server", "mcp_server.py")
    srv._embedder   = srv.Embedder()
    srv._collection = srv.build_index(srv._embedder)
    print()

    print("Loading client module...")
    client_mod = load_module("client", "mcp_client.py")
    print()

    run_unit        = not args.integration_only
    run_integration = not args.unit_only

    if run_unit:
        run_unit_tests(srv)

    if run_integration:
        run_integration_tests(srv, client_mod, port=args.port)

    total = passed + failed
    print(f"\n══ Results: {passed}/{total} passed", end="")
    print(f"  ({failed} failed)" if failed else "  — all tests passed ✓")
    print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
