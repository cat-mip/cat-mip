"""
mcp-client.py
─────────────
Sample client for the CAT-MIP MCP server (fastmcp 3.x, HTTP transport).

Connects to /mcp, performs the MCP initialize handshake, captures the
session ID returned by the server, and includes it in all subsequent
requests via the mcp-session-id header.

Usage:
  # Start the server first:
  python scripts/mcp/mcp-server.py --http

  # Then in another terminal:
  python scripts/mcp/mcp-client.py "what should I do with the account?"
  python scripts/mcp/mcp-client.py "WMI" --n 5
  python scripts/mcp/mcp-client.py --peek
  python scripts/mcp/mcp-client.py --peek --limit 3
  python scripts/mcp/mcp-client.py --server http://remote-host:8000 "backup policy"
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


class CatMipClient:
    """
    MCP client for the CAT-MIP server (fastmcp 3.x HTTP transport).

    Protocol:
      1. POST /mcp  initialize          → server returns mcp-session-id header
      2. POST /mcp  notifications/initialized  (include session ID header)
      3. POST /mcp  tools/call ...      (include session ID header)
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base       = base_url.rstrip("/")
        self._url        = f"{self._base}/mcp"
        self._session_id: str | None = None
        self._call_id    = 0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _headers(self) -> dict:
        """Build request headers, including session ID once we have one."""
        h = {
            "Content-Type": "application/json",
            "Accept":       "application/json, text/event-stream",
        }
        if self._session_id:
            h["mcp-session-id"] = self._session_id
        return h

    def _next_id(self) -> int:
        self._call_id += 1
        return self._call_id

    def _post(self, payload: dict) -> dict:
        """
        POST payload to /mcp, capture session ID from response headers,
        parse and return the JSON-RPC response body.
        """
        payload.setdefault("jsonrpc", "2.0")

        req = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode(),
            headers=self._headers(),
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                # Capture session ID from response headers
                sid = resp.headers.get("mcp-session-id")
                if sid:
                    self._session_id = sid

                raw = resp.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            raise RuntimeError(
                f"HTTP {e.code} {e.reason}\n"
                f"Response: {body[:300].decode('utf-8', errors='replace')}"
            )

        if not raw.strip():
            return {}

        # Server returns SSE-formatted lines: "event: message\r\ndata: {...}"
        # Extract the JSON from the data: line
        text = raw.decode()
        for line in text.splitlines():
            if line.startswith("data:"):
                text = line[5:].strip()
                break

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, timeout: float = 10.0) -> None:
        """
        Initialize the MCP session.

        Sends the initialize handshake, captures the mcp-session-id from
        the response headers, then sends the notifications/initialized
        confirmation — both required by the MCP protocol before tool calls.
        """
        deadline = time.time() + timeout
        last_err = ""

        while time.time() < deadline:
            try:
                # Step 1 — initialize (response contains mcp-session-id)
                self._post({
                    "id":     self._next_id(),
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities":    {},
                        "clientInfo":      {"name": "mcp-client", "version": "0.1"},
                    },
                })

                # Step 2 — notify server we are ready (session ID now in headers)
                self._post({
                    "method": "notifications/initialized",
                    "params": {},
                })

                return

            except RuntimeError as e:
                last_err = str(e)
                time.sleep(0.4)
            except Exception as e:
                last_err = str(e)
                time.sleep(0.4)

        raise ConnectionError(
            f"Could not connect to {self._url} after {timeout}s.\n"
            f"Last error: {last_err}"
        )

    # ── Tool calls ────────────────────────────────────────────────────────────

    def _call(self, tool: str, arguments: dict) -> list | dict:
        """Send a tools/call request and return parsed results."""
        if not self._session_id:
            raise RuntimeError("Not connected — call connect() first")

        data = self._post({
            "id":     self._next_id(),
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        })

        if "error" in data:
            raise RuntimeError(f"Server error: {data['error']}")

        content = data.get("result", {}).get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])

        return data

    def fetch(self, text: str, n_results: int = 5) -> list[dict]:
        """Call chroma_fetch and return ranked matches."""
        result = self._call("chroma_fetch", {"text": text, "n_results": n_results})
        if not isinstance(result, list):
            raise RuntimeError(f"Expected list from chroma_fetch, got {type(result)}")
        return result

    def peek(self, limit: int = 5) -> dict:
        """Call chroma_peek and return the first N index entries."""
        result = self._call("chroma_peek", {"limit": limit})
        if not isinstance(result, dict):
            raise RuntimeError(f"Expected dict from chroma_peek, got {type(result)}")
        return result


# ── Output helpers ────────────────────────────────────────────────────────────

def print_fetch_results(results: list[dict], query: str) -> None:
    print(f"\nQuery: {query!r}")
    for i, hit in enumerate(results, 1):
        divider = "─" * 60
        print(f"\n{divider}")
        print(f"  {i}. [{hit['relevance_score']:.4f}]  {hit['term']}")
        print(divider)
        print(hit["body"])
    print()


def print_peek_results(result: dict) -> None:
    print(f"\nIndex contains {result['total_docs']} documents")
    print("─" * 60)
    for item in result["peek"]:
        print(f"  [{item['id']}]  {item['term']}")
        print(f"         {item['body'][:120]}...")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="CAT-MIP MCP client")
    parser.add_argument(
        "query", nargs="?",
        default="what should I do with the account that's offline?",
        help="Text to disambiguate (ignored if --peek is set)",
    )
    parser.add_argument("--n",      type=int, default=5,
                        help="Number of fetch results (default 5)")
    parser.add_argument("--peek",   action="store_true",
                        help="Call chroma_peek instead of chroma_fetch")
    parser.add_argument("--limit",  type=int, default=5,
                        help="Number of peek results (default 5)")
    parser.add_argument("--server", default="http://localhost:8000",
                        help="MCP server base URL (default http://localhost:8000)")
    args = parser.parse_args()

    client = CatMipClient(args.server)

    print(f"Connecting to {args.server}/mcp ...")
    try:
        client.connect()
    except ConnectionError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Connected  (session: {client._session_id})")

    if args.peek:
        result = client.peek(limit=args.limit)
        print_peek_results(result)
    else:
        results = client.fetch(args.query, n_results=args.n)
        print_fetch_results(results, args.query)


if __name__ == "__main__":
    main()
