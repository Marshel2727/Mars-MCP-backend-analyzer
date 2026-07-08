# Demo Codex Flow

This demo shows how Codex should use Mars MCP for a real backend analysis task.

## Example Request

```text
Gunakan Mars untuk analisis backend Python project:
C:\PROJECT WEB\mars_bucket\buket_backend

Berikan alur kerja end-to-end.
```

## Expected Tool Flow

Codex should avoid reading many full files immediately. The preferred sequence:

```text
1. mars_plan_task
2. mars_project_brief
3. mars_find_relevant_files
4. mars_outline_file
5. mars_read_lines
6. final answer
```

## Step 1: Plan

Tool:

```text
mars_plan_task
```

Example arguments:

```json
{
  "project_path": "C:\\PROJECT WEB\\mars_bucket\\buket_backend",
  "question": "Berikan alur kerja end-to-end.",
  "depth": "normal"
}
```

Purpose:

- detect intent, such as `workflow`
- decide which tools should run next
- produce candidate files
- define the stop condition
- make the analysis process visible before reading code

## Step 2: Brief

Tool:

```text
mars_project_brief
```

Purpose:

- identify project type
- show top folders
- list entrypoints
- group files by backend layer
- suggest next files

## Step 3: Relevant Files

Tool:

```text
mars_find_relevant_files
```

Purpose:

- select a small set of files related to the user question
- include short reasons and symbols
- avoid sending full code too early

## Step 4: Outline Before Reading

Tool:

```text
mars_outline_file
```

Purpose:

- inspect classes/functions/routes quickly
- choose exact regions for `mars_read_lines`
- avoid unnecessary full-file reads

## Step 5: Read Small Ranges

Tool:

```text
mars_read_lines
```

Example arguments:

```json
{
  "project_path": "C:\\PROJECT WEB\\mars_bucket\\buket_backend",
  "file_path": "app/main.py",
  "start_line": 1,
  "end_line": 80,
  "max_lines": 80,
  "reason": "cek entrypoint aplikasi dan inisialisasi backend"
}
```

Expected output includes a visible file header:

```text
[MARS READ LINES]
file: app/main.py
lines: 1-80
reason: cek entrypoint aplikasi dan inisialisasi backend
--- content ---
...
```

## Step 6: Final Answer

Codex should synthesize the answer from:

- project brief
- relevant files
- outlines
- selected line reads

Do not paste raw full-file content unless the user asks for it.

## Example Final Format

```text
## Ringkasan Alur
...

## Alur End-to-End
...

## Peran Komponen
...

## File yang Dicek
...

## Batasan Analisis
...
```

## Bad Flow To Avoid

```text
mars_read_file
-> mars_read_file
-> mars_read_file
-> final answer
```

That flow hides the plan, costs more tokens, and makes it harder to understand
why each file was read.
