import json
import sys
import traceback
from typing import Any, Callable

from core.agent_runner import run_read_only_agent
from core.intent_profiles import detect_agent_intent, resolve_required_files
from core.planner import build_task_plan
from core.project_brief import build_project_brief
from core.project_map import build_project_map
from core.project_scanner import scan_project
from core.relevance import find_relevant_files
from tools.outline_file import outline_file
from tools.read_file import read_file
from tools.read_lines import read_lines
from tools.search_code import search_code


SERVER_NAME = "mars-project-analyzer"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"


class McpError(Exception):
  def __init__(self, code: int, message: str):
    self.code = code
    self.message = message
    super().__init__(message)


def main() -> None:
  for line in sys.stdin:
    if not line.strip():
      continue

    try:
      request = json.loads(line)
      response = handle_request(request)
    except Exception as error:
      response = build_error_response(None, -32603, format_exception(error))

    if response is not None:
      write_message(response)


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
  request_id = request.get("id")
  method = request.get("method")
  params = request.get("params") or {}

  if method and method.startswith("notifications/"):
    return None

  try:
    if method == "initialize":
      return build_result_response(request_id, initialize_result(params))

    if method == "ping":
      return build_result_response(request_id, {})

    if method == "tools/list":
      return build_result_response(request_id, {"tools": get_tools()})

    if method == "tools/call":
      return build_result_response(request_id, call_tool(params))

    if method in {"resources/list", "prompts/list"}:
      return build_result_response(request_id, {method.split("/")[0]: []})

    raise McpError(-32601, f"Method not found: {method}")
  except McpError as error:
    return build_error_response(request_id, error.code, error.message)
  except Exception as error:
    return build_error_response(request_id, -32603, format_exception(error))


def initialize_result(params: dict[str, Any]) -> dict[str, Any]:
  return {
    "protocolVersion": params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION),
    "capabilities": {
      "tools": {},
    },
    "serverInfo": {
      "name": SERVER_NAME,
      "version": SERVER_VERSION,
    },
  }


def get_tools() -> list[dict[str, Any]]:
  return [
    {
      "name": "mars_scan_project",
      "description": "List backend-focused files detected in a project.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
      }, required=["project_path"]),
    },
    {
      "name": "mars_project_map",
      "description": "Build a compact project map with Python symbols.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "max_files": integer_schema("Maximum files to include.", default=200, minimum=1, maximum=500),
        "max_symbols": integer_schema("Maximum symbols per file.", default=12, minimum=0, maximum=50),
      }, required=["project_path"]),
    },
    {
      "name": "mars_project_brief",
      "description": "Return a small compressed project structure brief. Prefer this before project_map to keep input tokens low.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "max_files_per_layer": integer_schema("Maximum files to show per detected layer.", default=5, minimum=1, maximum=20),
        "max_symbols": integer_schema("Maximum symbols to show per file.", default=4, minimum=0, maximum=20),
      }, required=["project_path"]),
    },
    {
      "name": "mars_plan_task",
      "description": "Create a read-only analysis plan before running other Mars tools. Use this first for larger backend questions.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "question": string_schema("User question or analysis request."),
        "depth": enum_schema(["quick", "normal", "deep"], default="normal"),
      }, required=["project_path", "question"]),
    },
    {
      "name": "mars_backend_strategy_files",
      "description": "Resolve the backend Python files Mars would prioritize for a question.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "question": string_schema("User question or analysis request."),
        "depth": enum_schema(["quick", "normal", "deep"], default="normal"),
      }, required=["project_path", "question"]),
    },
    {
      "name": "mars_find_relevant_files",
      "description": "Find a small set of files relevant to a question, with short reasons and symbols.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "question": string_schema("User question or analysis request."),
        "max_files": integer_schema("Maximum relevant files to return.", default=8, minimum=1, maximum=50),
        "max_symbols": integer_schema("Maximum symbols to show per file.", default=6, minimum=0, maximum=20),
      }, required=["project_path", "question"]),
    },
    {
      "name": "mars_search_code",
      "description": "Search text in backend-focused project files.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "query": string_schema("Search keyword or text."),
        "max_results": integer_schema("Maximum matches to return.", default=20, minimum=1, maximum=200),
      }, required=["project_path", "query"]),
    },
    {
      "name": "mars_outline_file",
      "description": "Return a lightweight outline of one source file.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "file_path": string_schema("Project-relative file path."),
      }, required=["project_path", "file_path"]),
    },
    {
      "name": "mars_read_lines",
      "description": "Read only a line range from a project-relative file. Prefer this over mars_read_file for token control. The result includes a visible file header.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "file_path": string_schema("Project-relative file path."),
        "start_line": integer_schema("First line to read, 1-based.", minimum=1),
        "end_line": integer_schema("Last line to read, inclusive.", minimum=1),
        "max_lines": integer_schema("Safety cap for returned lines.", default=200, minimum=1, maximum=500),
        "reason": string_schema("Optional short reason why this file/range is being read."),
      }, required=["project_path", "file_path", "start_line", "end_line"]),
    },
    {
      "name": "mars_read_file",
      "description": "Read a project-relative file. Use only when exact code is needed. The result includes a visible file header.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "file_path": string_schema("Project-relative file path."),
        "reason": string_schema("Optional short reason why this file is being read."),
      }, required=["project_path", "file_path"]),
    },
    {
      "name": "mars_analyze_backend",
      "description": "Run Mars read-only backend Python analysis through local Ollama.",
      "inputSchema": object_schema({
        "project_path": string_schema("Absolute or relative path to the project."),
        "question": string_schema("User question or analysis request."),
        "depth": enum_schema(["quick", "normal", "deep"], default="normal"),
        "max_steps": integer_schema("Optional maximum agent steps.", minimum=1, maximum=30),
      }, required=["project_path", "question"]),
    },
  ]


def call_tool(params: dict[str, Any]) -> dict[str, Any]:
  tool_name = params.get("name")
  arguments = params.get("arguments") or {}
  tool = TOOL_HANDLERS.get(tool_name)

  if not tool:
    raise McpError(-32602, f"Unknown tool: {tool_name}")

  result = tool(arguments)

  return {
    "content": [
      {
        "type": "text",
        "text": stringify_tool_result(result),
      }
    ]
  }


def tool_scan_project(arguments: dict[str, Any]) -> list[str]:
  project_path = require_string(arguments, "project_path")

  return [str(file_path).replace("\\", "/") for file_path in scan_project(project_path)]


def tool_project_map(arguments: dict[str, Any]) -> str:
  project_path = require_string(arguments, "project_path")
  max_files = require_int(arguments, "max_files", default=200, minimum=1, maximum=500)
  max_symbols = require_int(arguments, "max_symbols", default=12, minimum=0, maximum=50)

  return build_project_map(
    project_path,
    max_files=max_files,
    max_symbols_per_file=max_symbols,
  )


def tool_project_brief(arguments: dict[str, Any]) -> dict[str, Any]:
  project_path = require_string(arguments, "project_path")
  max_files_per_layer = require_int(
    arguments,
    "max_files_per_layer",
    default=5,
    minimum=1,
    maximum=20,
  )
  max_symbols = require_int(arguments, "max_symbols", default=4, minimum=0, maximum=20)

  return build_project_brief(
    project_path,
    max_files_per_layer=max_files_per_layer,
    max_symbols=max_symbols,
  )


def tool_plan_task(arguments: dict[str, Any]) -> dict[str, Any]:
  project_path = require_string(arguments, "project_path")
  question = require_string(arguments, "question")
  depth = str(arguments.get("depth") or "normal")

  return build_task_plan(project_path, question, depth=depth)


def tool_backend_strategy_files(arguments: dict[str, Any]) -> dict[str, Any]:
  project_path = require_string(arguments, "project_path")
  question = require_string(arguments, "question")
  depth = str(arguments.get("depth") or "normal")
  intent = detect_agent_intent(question)
  files = resolve_required_files(project_path, intent, depth)

  return {
    "intent": intent,
    "depth": depth,
    "files": list(files),
  }


def tool_find_relevant_files(arguments: dict[str, Any]) -> list[dict[str, Any]]:
  project_path = require_string(arguments, "project_path")
  question = require_string(arguments, "question")
  max_files = require_int(arguments, "max_files", default=8, minimum=1, maximum=50)
  max_symbols = require_int(arguments, "max_symbols", default=6, minimum=0, maximum=20)

  return find_relevant_files(
    project_path,
    question,
    max_files=max_files,
    max_symbols=max_symbols,
  )


def tool_search_code(arguments: dict[str, Any]) -> list[dict[str, Any]]:
  project_path = require_string(arguments, "project_path")
  query = require_string(arguments, "query")
  max_results = require_int(arguments, "max_results", default=20, minimum=1, maximum=200)

  return search_code(project_path, query, max_results=max_results)


def tool_outline_file(arguments: dict[str, Any]) -> str:
  project_path = require_string(arguments, "project_path")
  file_path = require_string(arguments, "file_path")

  return outline_file(project_path, file_path)


def tool_read_file(arguments: dict[str, Any]) -> str:
  project_path = require_string(arguments, "project_path")
  file_path = require_string(arguments, "file_path")
  reason = optional_string(arguments, "reason")
  content = read_file(project_path, file_path)

  return format_file_result(
    "MARS READ FILE",
    file_path,
    content,
    reason=reason,
  )


def tool_read_lines(arguments: dict[str, Any]) -> str:
  project_path = require_string(arguments, "project_path")
  file_path = require_string(arguments, "file_path")
  start_line = require_int(arguments, "start_line", default=1, minimum=1)
  end_line = require_int(arguments, "end_line", default=start_line, minimum=1)
  max_lines = require_int(arguments, "max_lines", default=200, minimum=1, maximum=500)
  reason = optional_string(arguments, "reason")
  content = read_lines(
    project_path,
    file_path,
    start_line,
    end_line,
    max_lines=max_lines,
  )

  return format_file_result(
    "MARS READ LINES",
    file_path,
    content,
    reason=reason,
    line_range=f"{start_line}-{end_line}",
  )


def tool_analyze_backend(arguments: dict[str, Any]) -> str:
  from llm.ollama_provider import OllamaProvider

  project_path = require_string(arguments, "project_path")
  question = require_string(arguments, "question")
  depth = str(arguments.get("depth") or "normal")
  max_steps = arguments.get("max_steps")

  if max_steps is not None:
    max_steps = require_int(arguments, "max_steps", minimum=1, maximum=30)

  return run_read_only_agent(
    project_path,
    question,
    OllamaProvider(),
    max_steps=max_steps,
    depth=depth,
    verbose=False,
  )


TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
  "mars_scan_project": tool_scan_project,
  "mars_project_map": tool_project_map,
  "mars_project_brief": tool_project_brief,
  "mars_plan_task": tool_plan_task,
  "mars_backend_strategy_files": tool_backend_strategy_files,
  "mars_find_relevant_files": tool_find_relevant_files,
  "mars_search_code": tool_search_code,
  "mars_outline_file": tool_outline_file,
  "mars_read_lines": tool_read_lines,
  "mars_read_file": tool_read_file,
  "mars_analyze_backend": tool_analyze_backend,
}


def object_schema(
  properties: dict[str, Any],
  required: list[str] | None = None,
) -> dict[str, Any]:
  return {
    "type": "object",
    "properties": properties,
    "required": required or [],
    "additionalProperties": False,
  }


def string_schema(description: str) -> dict[str, Any]:
  return {
    "type": "string",
    "description": description,
  }


def integer_schema(
  description: str,
  default: int | None = None,
  minimum: int | None = None,
  maximum: int | None = None,
) -> dict[str, Any]:
  schema = {
    "type": "integer",
    "description": description,
  }

  if default is not None:
    schema["default"] = default

  if minimum is not None:
    schema["minimum"] = minimum

  if maximum is not None:
    schema["maximum"] = maximum

  return schema


def enum_schema(values: list[str], default: str) -> dict[str, Any]:
  return {
    "type": "string",
    "enum": values,
    "default": default,
  }


def require_string(arguments: dict[str, Any], key: str) -> str:
  value = arguments.get(key)

  if not isinstance(value, str) or not value.strip():
    raise McpError(-32602, f"Missing required string argument: {key}")

  return value


def optional_string(arguments: dict[str, Any], key: str) -> str | None:
  value = arguments.get(key)

  if value is None:
    return None

  if not isinstance(value, str):
    raise McpError(-32602, f"Argument must be a string: {key}")

  value = value.strip()

  if not value:
    return None

  return value


def require_int(
  arguments: dict[str, Any],
  key: str,
  default: int | None = None,
  minimum: int | None = None,
  maximum: int | None = None,
) -> int:
  value = arguments.get(key, default)

  if value is None:
    raise McpError(-32602, f"Missing required integer argument: {key}")

  try:
    int_value = int(value)
  except (TypeError, ValueError):
    raise McpError(-32602, f"Argument must be an integer: {key}")

  if minimum is not None and int_value < minimum:
    raise McpError(-32602, f"Argument {key} must be >= {minimum}")

  if maximum is not None and int_value > maximum:
    raise McpError(-32602, f"Argument {key} must be <= {maximum}")

  return int_value


def format_file_result(
  title: str,
  file_path: str,
  content: str,
  reason: str | None = None,
  line_range: str | None = None,
) -> str:
  header = [
    f"[{title}]",
    f"file: {file_path}",
  ]

  if line_range:
    header.append(f"lines: {line_range}")

  if reason:
    header.append(f"reason: {reason}")

  header.append("--- content ---")

  return "\n".join(header) + "\n" + content


def stringify_tool_result(result: Any) -> str:
  if isinstance(result, str):
    return result

  return json.dumps(result, ensure_ascii=False, indent=2)


def build_result_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
  return {
    "jsonrpc": "2.0",
    "id": request_id,
    "result": result,
  }


def build_error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
  return {
    "jsonrpc": "2.0",
    "id": request_id,
    "error": {
      "code": code,
      "message": message,
    },
  }


def write_message(message: dict[str, Any]) -> None:
  sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")))
  sys.stdout.write("\n")
  sys.stdout.flush()


def format_exception(error: Exception) -> str:
  if isinstance(error, McpError):
    return error.message

  return "".join(traceback.format_exception_only(type(error), error)).strip()


if __name__ == "__main__":
  main()
