# CAT-MIP MCP Server — Setup Guide

Step-by-step instructions for getting the server running in VS Code,
connecting it to Claude Desktop, and connecting it to Gemini.

---

## Prerequisites

Before you start you need the following installed on your machine.

### Python 3.11 or later

```bash
# Check your version
python3 --version
```

If you need to install Python, download it from https://python.org/downloads.
On macOS you can also use Homebrew:

```bash
brew install python@3.11
```

### Git

```bash
git --version
```

Download from https://git-scm.com if not installed.

### VS Code

Download from https://code.visualstudio.com if not installed.

---

## Part 1 — Getting the code

### Step 1 — Clone the repository

Open a terminal and run:

```bash
git clone https://github.com/cat-mip/cat-mip.git
cd cat-mip
```

### Step 2 — Open in VS Code

```bash
code .
```

Or open VS Code manually and use **File → Open Folder**, select the
`cat-mip` folder you just cloned.

---

## Part 2 — Setting up the Python environment in VS Code

### Step 3 — Open the integrated terminal

In VS Code press `` Ctrl+` `` (Windows/Linux) or `` Cmd+` `` (macOS) to
open the integrated terminal. All remaining commands in this section are
run here.

### Step 4 — Create a virtual environment

```bash
python3 -m venv .venv
```

This creates a `.venv` folder at the root of the project.

### Step 5 — Activate the virtual environment

**macOS / Linux:**
```bash
source .venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` appear at the start of your terminal prompt
confirming the environment is active.

### Step 6 — Select the Python interpreter in VS Code

1. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS) to
   open the Command Palette
2. Type `Python: Select Interpreter` and press Enter
3. Select the interpreter that shows `.venv` in the path, e.g.
   `./.venv/bin/python` (macOS/Linux) or `.\.venv\Scripts\python.exe`
   (Windows)

VS Code will now use this interpreter for all Python features including
IntelliSense, debugging, and the terminal.

### Step 7 — Install dependencies

```bash
pip install -r scripts/mcp/requirements.txt
```

This installs all required packages into the virtual environment. The
first install takes a minute or two — `sentence-transformers` pulls in
PyTorch.

You should see output ending with something like:

```
Successfully installed chromadb-0.5.x fastmcp-3.x.x sentence-transformers-3.x.x ...
```

---

## Part 3 — Building the data files

### Step 8 — Build the flat JSON

The MCP server reads from `build/cat-mip-flat.json`. Generate it from
the YAML source files:

```bash
python scripts/build_flat_json.py
```

Expected output:

```
Building flat JSON for ChromaDB ingestion...
  Wrote  78 terms → build/cat-mip-chroma.json
  Wrote  85 terms → build/cat-mip-chroma-dev.json
Done.
```

Confirm the file exists:

```bash
ls build/
# cat-mip-chroma.json   cat-mip-chroma-dev.json
```

> **Note:** The server reads `build/cat-mip-flat.json`. If your build
> script writes a different filename, check that `JSON_FILE` in
> `mcp-server.py` matches.

---

## Part 4 — Running the server in VS Code

You can run the server two ways — from the terminal or using VS Code's
built-in debugger.

### Option A — Run from the terminal

**stdio mode** (for Claude Desktop, no port needed):
```bash
python scripts/mcp/mcp-server.py
```

**HTTP mode** (for testing with the client or remote access):
```bash
python scripts/mcp/mcp-server.py --http
```

Expected startup output:

```
CAT-MIP server starting...
.   Loading model: all-MiniLM-L6-v2
  Ingesting 78 terms from cat-mip-flat.json...
.   Index ready - 78 docs
Transport: HTTP/SSE on 0.0.0.0:8000
```

The server is ready when you see the `Transport:` line.

### Option B — Run and debug in VS Code

1. Open `scripts/mcp/mcp-server.py` in the editor
2. Click **Run → Add Configuration** (or open `.vscode/launch.json`
   manually)
3. Add the following configurations:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "CAT-MIP Server (stdio)",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/scripts/mcp/mcp-server.py",
            "python": "${workspaceFolder}/.venv/bin/python",
            "console": "integratedTerminal"
        },
        {
            "name": "CAT-MIP Server (HTTP)",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/scripts/mcp/mcp-server.py",
            "args": ["--http"],
            "python": "${workspaceFolder}/.venv/bin/python",
            "console": "integratedTerminal"
        },
        {
            "name": "CAT-MIP Client",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/scripts/mcp/mcp-client.py",
            "args": ["what is an account in MSP context?"],
            "python": "${workspaceFolder}/.venv/bin/python",
            "console": "integratedTerminal"
        }
    ]
}
```

4. On Windows, replace `bin/python` with `Scripts/python.exe`
5. Select **CAT-MIP Server (HTTP)** from the Run and Debug dropdown
6. Press `F5` to start — you can set breakpoints in the server code and
   they will be hit when the client calls a tool

---

## Part 5 — Running the client

With the HTTP server running (from Part 4), open a **second terminal**
in VS Code by clicking the `+` icon in the terminal panel.

Make sure the virtual environment is active in the new terminal:

```bash
source .venv/bin/activate   # macOS/Linux
# or
.venv\Scripts\activate      # Windows
```

### Basic query

```bash
python scripts/mcp/mcp-client.py "what is an account?"
```

Expected output:

```
Connecting to http://localhost:8000/mcp ...
Connected  (session: a1b2c3d4...)

Query: 'what is an account?'
────────────────────────────────────────────────────────────
  1. [0.7823]  Account
────────────────────────────────────────────────────────────
The term Account is discouraged due to its ambiguity...

  2. [0.7102]  Tenant
...
```

### Peek at the index

```bash
python scripts/mcp/mcp-client.py --peek
```

### More examples

```bash
# Acronym lookup
python scripts/mcp/mcp-client.py "WMI"

# More results
python scripts/mcp/mcp-client.py "backup and restore" --n 8

# Peek with custom limit
python scripts/mcp/mcp-client.py --peek --limit 10

# Remote server
python scripts/mcp/mcp-client.py "patch policy" --server http://192.168.1.100:8000
```

---

## Part 6 — Connecting to Claude Desktop

Claude Desktop uses **stdio mode** — it launches the server as a child
process and communicates through stdin/stdout. No port is needed.

### Step 1 — Find the Claude Desktop config file

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

If the file does not exist, create it.

### Step 2 — Find your Python interpreter path

In VS Code terminal (with venv active):

**macOS/Linux:**
```bash
which python
# example output: /Users/yourname/Documents/GitHub/cat-mip/.venv/bin/python
```

**Windows:**
```cmd
where python
# example output: C:\Users\yourname\Documents\GitHub\cat-mip\.venv\Scripts\python.exe
```

Copy the full path — you will need it in the next step.

### Step 3 — Edit the config file

Open `claude_desktop_config.json` in VS Code or any text editor and add
the `cat-mip` entry. If the file is empty, paste the whole block. If it
already has other servers, add the `cat-mip` entry inside the existing
`mcpServers` object.

**macOS/Linux:**

```json
{
  "mcpServers": {
    "cat-mip": {
      "command": "/Users/yourname/Documents/GitHub/cat-mip/.venv/bin/python",
      "args": [
        "/Users/yourname/Documents/GitHub/cat-mip/scripts/mcp/mcp-server.py"
      ]
    }
  }
}
```

**Windows:**

```json
{
  "mcpServers": {
    "cat-mip": {
      "command": "C:\\Users\\yourname\\Documents\\GitHub\\cat-mip\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\yourname\\Documents\\GitHub\\cat-mip\\scripts\\mcp\\mcp-server.py"
      ]
    }
  }
}
```

> **Important:** Use full absolute paths. Relative paths will not work
> because Claude Desktop launches the server from a different working
> directory.

> **Windows note:** Use double backslashes `\\` in the JSON, or forward
> slashes `/` — both work.

### Step 4 — Restart Claude Desktop

Fully quit and relaunch Claude Desktop. On macOS use
`Cmd+Q`, not just closing the window.

### Step 5 — Verify the tool is available

In a new Claude conversation, click the tools icon (hammer) in the
bottom left of the message input. You should see `cat-mip` listed with
the `chroma_fetch` and `chroma_peek` tools.

You can also type a prompt that would trigger disambiguation:

```
Using the cat-mip tool, what is the canonical term for "account" in an MSP context?
```

Claude will call `chroma_fetch` automatically and return the results.

### Troubleshooting Claude Desktop

**Tool does not appear:**
- Check the config file is valid JSON (paste it into https://jsonlint.com)
- Confirm the Python path and script path both exist
- Check Claude Desktop logs: **macOS** — `~/Library/Logs/Claude/`,
  **Windows** — `%APPDATA%\Claude\logs\`

**Server crashes on startup:**
- Test the command manually in a terminal:
  ```bash
  /full/path/to/.venv/bin/python /full/path/to/scripts/mcp/mcp-server.py
  ```
  If it errors, the error will be visible in the terminal

**`build/cat-mip-flat.json` not found:**
- The server starts from a different working directory when launched by
  Claude Desktop. The path constants in `mcp-server.py` use
  `Path(__file__).parent` to resolve paths relative to the script file
  itself, so this should not be an issue — but confirm that
  `build/cat-mip-flat.json` exists in the repo root

---


## Quick reference

### Start the server

```bash
# Activate venv first
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# stdio (Claude Desktop)
python scripts/mcp/mcp-server.py

# HTTP (client, Gemini, remote)
python scripts/mcp/mcp-server.py --http

# Custom port
python scripts/mcp/mcp-server.py --http --port 9000
```

### Run the client

```bash
python scripts/mcp/mcp-client.py "your query here"
python scripts/mcp/mcp-client.py --peek
python scripts/mcp/mcp-client.py "WMI" --n 5
```

### Rebuild the index

Run this after pulling new CAT-MIP YAML changes:

```bash
python scripts/build_flat_json.py
rm -rf scripts/mcp/cat-mip-chroma/
python scripts/mcp/mcp-server.py --http
```

### Verify server is running

```bash
# Check the port is open
lsof -i :8000          # macOS/Linux
netstat -ano | findstr :8000   # Windows

# Check the MCP endpoint responds
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"0.1"}}}'
```

---

## File reference

```
cat-mip/
├── build/
│   ├── cat-mip-flat.json          ← generated by build_flat_json.py
│   └── cat-mip-chroma.json
├── scripts/
│   ├── build_flat_json.py         ← step 1: YAML → flat JSON
│   └── mcp/
│       ├── mcp-server.py          ← MCP server
│       ├── mcp-client.py          ← sample client
│       ├── cat-mip-chroma/        ← ChromaDB store (auto-created)
│       ├── requirements.txt
│       ├── README.md
│       ├── TESTING.md
│       └── SETUP.md               ← this file
└── standards/
    ├── accepted/                  ← source YAML files
    └── draft/
```
