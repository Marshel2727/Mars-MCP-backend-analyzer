# Mars MCP Backend Analyzer

Mars MCP Backend Analyzer is a local, read-only analyzer for Python backend
projects. It is built to work well with Codex and other MCP clients by exposing
small, focused tools instead of dumping an entire repository into the model
context.

The project focus is simple:

- scan Python backend projects safely
- build compact project maps and project briefs
- find files relevant to a user question
- outline source files before reading them
- read only specific line ranges when possible
- provide a planning step before larger analysis work

## Why This Exists

Large codebases are expensive to send to an AI model. Mars works as a local
indexer and context compressor:

```text
User question
-> mars_plan_task
-> mars_project_brief
-> mars_find_relevant_files
-> mars_outline_file / mars_search_code
-> mars_read_lines
-> final answer from Codex or another AI client
```

This keeps token usage lower and makes the analysis process easier to monitor.

## Features

- Read-only MCP server over stdio
- CLI fallback for local use
- Backend-focused file scanner
- Ignore rules for `.env`, virtual environments, caches, build output, binary
  files, and common dependency folders
- Project brief and project map tools
- Relevant file selection
- File outline and line-range reading
- Deterministic task planner
- Optional Ollama agent mode

## MCP Tools

Mars exposes these tools:

- `mars_plan_task`
- `mars_project_brief`
- `mars_find_relevant_files`
- `mars_project_map`
- `mars_backend_strategy_files`
- `mars_scan_project`
- `mars_search_code`
- `mars_outline_file`
- `mars_read_lines`
- `mars_read_file`
- `mars_analyze_backend`

Prefer the low-token flow:

```text
mars_plan_task
-> mars_project_brief
-> mars_find_relevant_files
-> mars_outline_file or mars_search_code
-> mars_read_lines
-> final answer
```

Use `mars_read_file` only when exact full-file context is required.

## Install

```bash
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

On Git Bash or Linux-like shells:

```bash
python -m venv venv
source venv/Scripts/activate
python -m pip install -r requirements.txt
```

## CLI Usage

Show a compact project brief:

```bash
./mars project-brief "C:\path\to\backend"
```

Create a plan before analysis:

```bash
./mars plan "C:\path\to\backend" "berikan alur kerja backend ini" --depth normal
```

Find relevant files:

```bash
./mars relevant-files "C:\path\to\backend" "debug error login"
```

Read only a small range:

```bash
./mars read-lines "C:\path\to\backend" app/main.py 1 80
```

Run the optional Ollama agent:

```bash
./mars agent "C:\path\to\backend" "analisis project ini" --depth normal
```

## Codex MCP Config

Example Codex config:

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

After changing the MCP server code or tool schema, restart Codex or reconnect
the MCP server so the updated tools are loaded.

## Token Benchmark

The exact token count depends on project size and the question, but the expected
shape is:

| Approach | Context sent to model | Expected token use | Notes |
| --- | --- | ---: | --- |
| Without Mars MCP | Many full files copied manually | High | Simple but wasteful for large projects |
| With `mars_project_map` | Compact file list and symbols | Medium | Good for overview questions |
| With `mars_project_brief` + `mars_find_relevant_files` + `mars_read_lines` | Brief, selected files, and small line ranges | Low | Best default for Codex workflows |

See [docs/token-benchmark.md](docs/token-benchmark.md) for the benchmark
template.

## Testing

Run the test suite:

```bash
pytest
```

Current coverage focuses on the safety-critical local tools:

- path traversal protection
- `.env` blocking
- ignored directory scanning
- line read limits
- search line numbers

## Safety Model

Mars is intended to be read-only. The MCP tools are designed to inspect a local
project, not modify it. Keep write operations in the AI/client layer explicit
and separate from Mars.

## Documentation

- [Codex integration](CODEX_INTEGRATION.md)
- [Codex demo flow](docs/demo-codex-flow.md)
- [Token benchmark](docs/token-benchmark.md)
