# Mars Project Analyzer

Mars is a local read-only project analyzer focused on Python backend projects.

When analyzing a backend project, prefer these Mars tools before reading many files manually:

- Use `mars_plan_task` first for broad/debug/review questions so the analysis has a visible plan.
- Use `mars_project_brief` first to get a small compressed structure summary.
- Use `mars_find_relevant_files` to select a small file set for the user question.
- Use the MCP server tool `mars_project_map` to get a compact project map.
- Use `mars_backend_strategy_files` to identify the backend files Mars would prioritize for a question.
- Use `mars_outline_file` before `mars_read_file` for large files.
- Use `mars_read_lines` instead of `mars_read_file` whenever only a small code region is needed.
- Pass a short `reason` to `mars_read_file` or `mars_read_lines` when possible; their output includes a visible file header.
- Use `mars_analyze_backend` when the user wants Mars to run its local Ollama agent loop.

If MCP is not configured, use the CLI:

```bash
./mars agent "<project_path>" "<question>" --depth normal
```

Use `--depth quick` for a fast first pass and `--depth deep` for a more complete backend analysis.

Mars backend focus:

- Python entrypoints: `main.py`, `app.py`, `run.py`, `manage.py`, `wsgi.py`, `asgi.py`
- App initialization: Flask/FastAPI/Django app setup and factories
- Routing/API layer: routes, routers, controllers, views, endpoints
- Service/business layer
- Models, schemas, serializers, DTOs
- Database/session/repository/migrations
- Auth, security, middleware, permissions
- External providers, clients, adapters, integrations

Avoid using Mars as a write tool. It is intended for read-only analysis and synthesis.

Preferred low-token MCP flow:

```text
mars_plan_task
-> mars_project_brief
-> mars_find_relevant_files
-> mars_outline_file or mars_search_code
-> mars_read_lines
-> final answer
```

Use `mars_project_map` only when the brief is not enough, and use `mars_read_file`
only when exact full-file context is truly needed.
