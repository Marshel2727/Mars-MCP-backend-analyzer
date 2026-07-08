# Codex Integration

Mars can be exposed to Codex as a local MCP server.

## MCP Server

The server entrypoint is:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File mars-mcp.ps1
```

`mars-mcp.ps1` uses `python` by default. To force a specific interpreter, set
`MARS_MCP_PYTHON` before starting the server.

It communicates through stdio and exposes read-only tools:

- `mars_scan_project`
- `mars_project_brief`
- `mars_plan_task`
- `mars_project_map`
- `mars_find_relevant_files`
- `mars_backend_strategy_files`
- `mars_search_code`
- `mars_outline_file`
- `mars_read_lines`
- `mars_read_file`
- `mars_analyze_backend`

## Low-Token Workflow

Prefer this workflow in Codex:

```text
mars_plan_task
-> mars_project_brief
-> mars_find_relevant_files
-> mars_outline_file or mars_search_code
-> mars_read_lines
-> final answer
```

Use `mars_project_map` only when the brief is not enough. Use `mars_read_file`
only when exact full-file context is required. This keeps Mars acting as an indexer
and context compressor instead of sending a large project dump to Codex.

`mars_read_file` and `mars_read_lines` include a visible result header with the
file path. Pass the optional `reason` argument when a tool call is part of a plan
so the returned context explains why the file was read.

## Example Codex Config

Add a local MCP server entry similar to this in your Codex config:

```toml
[mcp_servers.mars]
command = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
args = [
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-File",
  "C:\\project AI\\Mars-MCP-backend-analyzer\\mars-mcp.ps1"
]
cwd = "C:\\project AI\\Mars-MCP-backend-analyzer"

[mcp_servers.mars.env]
MARS_MCP_PYTHON = "C:\\path\\to\\python.exe"
```

If your Codex client expects a different MCP config key, keep the same command,
args, and cwd values. Do not use `mars.ps1` as the MCP command because it prints
CLI status text; MCP stdout must contain only JSON-RPC messages.

If `mars_analyze_backend` fails because Python cannot import `requests`, install
the project dependencies for the Python used by `mars-mcp.ps1`:

```bash
python -m pip install -r requirements.txt
```

Or configure `MARS_MCP_PYTHON` to point at an environment that already has the
requirements installed.

## Usage

After connecting the MCP server, ask Codex things like:

```text
Use Mars to analyze this Python backend project:
C:\PROJECT WEB\mars_bucket\buket_backend

Explain the end-to-end workflow.
```

For local Ollama analysis, make sure Ollama is running and the model configured in
`.env` is available.

## CLI Fallback

If MCP is not available, use Mars directly:

```bash
./mars agent "C:\PROJECT WEB\mars_bucket\buket_backend" "berikan saya alur kerja dari project ini" --depth normal
```
