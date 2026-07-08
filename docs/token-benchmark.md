# Token Benchmark

This document gives a simple benchmark template for comparing analysis styles.

The numbers below are intentionally approximate. Measure real token counts from
your Codex or API logs for each project.

## Benchmark Question

```text
Berikan alur kerja end-to-end dari backend project ini.
```

## Comparison Table

| Approach | Tool flow | Example input shape | Token use | Best for |
| --- | --- | --- | ---: | --- |
| Without Mars MCP | Manual full-file reads | Many full source files | High | Small projects or exact deep code review |
| With `mars_project_map` | `mars_project_map -> final answer` | File list and symbols | Medium | Overview and architecture questions |
| With brief + relevance + line reads | `mars_project_brief -> mars_find_relevant_files -> mars_outline_file -> mars_read_lines -> final answer` | Compact summary plus selected snippets | Low | Default Codex workflow |

## Suggested Measurement Method

1. Ask the same question with no Mars MCP context.
2. Ask again using `mars_project_map`.
3. Ask again using the low-token Mars flow.
4. Record input, cached, output, and total token counts.

## Results Template

| Run | Input tokens | Cached tokens | Output tokens | Total tokens | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Without Mars MCP |  |  |  |  |  |
| With `mars_project_map` |  |  |  |  |  |
| With brief + relevant files + line reads |  |  |  |  |  |

## Interpretation

- Full-file reads usually increase input tokens quickly.
- `mars_project_map` is useful when file names and symbols are enough.
- `mars_project_brief` plus `mars_find_relevant_files` plus `mars_read_lines`
  usually gives the best balance between context quality and token cost.
