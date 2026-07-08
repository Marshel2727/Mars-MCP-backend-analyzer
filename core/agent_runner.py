import json
import re
import time
from typing import Any

from core.intent_profiles import (
  detect_agent_intent,
  get_depth_max_auto_steps,
  get_depth_max_steps,
  get_intent_focus,
  resolve_required_files,
  requires_required_files,
)
from core.project_map import build_project_map
from tools.list_folder import list_folder
from tools.outline_file import outline_file
from tools.read_file import read_file
from tools.search_code import search_code


MAX_NOTE_SOURCE_CHARS = 20000
MAX_AGENT_PARSE_RETRIES = 2
MAX_BATCH_READ_FILES = 5
ACTION_NUM_PREDICT = 512
NOTE_NUM_PREDICT = 512
FINAL_NUM_PREDICT = 1536
AGENT_TEMPERATURE = 0.0


class AgentError(Exception):
  pass


def run_read_only_agent(
  project_path: str,
  question: str,
  provider,
  max_steps: int | None = None,
  depth: str = "normal",
  verbose: bool = True,
) -> str:
  from llm.prompt_templates import build_agent_prompt

  intent = detect_agent_intent(question)
  required_files = resolve_required_files(project_path, intent, depth)
  effective_max_steps = resolve_effective_max_steps(depth, required_files, max_steps)
  intent_focus = get_intent_focus(intent)
  started_at = time.perf_counter()

  if verbose:
    print("[agent] Building project map...")

  project_map = build_project_map(project_path)
  history: list[dict[str, Any]] = []

  if verbose:
    print(f"[agent] Project map ready ({len(project_map)} chars)")
    print(
      f"[agent] Starting read-only analysis, "
      f"intent: {intent}, depth: {depth}, max steps: {effective_max_steps}"
    )

  bootstrap_strategy_files(
    provider,
    project_path,
    question,
    history,
    required_files,
    verbose,
  )

  for step_number in range(1, effective_max_steps + 1):
    prompt = build_agent_prompt(
      question,
      project_map,
      history,
      step_number,
      effective_max_steps,
      depth=depth,
      intent=intent,
      intent_focus=intent_focus,
      required_files=required_files,
    )

    if verbose:
      print(f"[agent step {step_number}] Asking model for next action...")

    try:
      action = ask_agent_for_action(provider, prompt, history, verbose)
    except AgentError as error:
      fallback_action = build_fallback_action(history, required_files)

      if not fallback_action:
        raise

      if verbose:
        print(f"[agent] Planner failed: {error}")
        print("[agent] Falling back to deterministic read of strategy files.")

      action = fallback_action
    action_name = action.get("action")

    if verbose:
      reason = action.get("reason", "")
      target = format_action_target(action)
      detail = f" {target}" if target else ""
      print(f"[agent step {step_number}] {action_name}{detail}")

      if reason:
        print(f"  reason: {reason}")

        if is_generic_reason(reason):
          print("  warning: reason masih generik; prompt mungkin perlu diperketat lagi.")

    if action_name == "answer":
      missing_files = get_missing_required_files(intent, history, required_files)

      if should_delay_answer(intent, missing_files, step_number, effective_max_steps):
        if verbose:
          print("[agent] Answer looked premature; asking model to inspect more context.")
          print(f"[agent] Missing required reads: {', '.join(missing_files)}")

        history.append({
          "action": action,
          "note": (
            "System feedback: jawaban terlalu cepat. "
            "Baca file strategi berikut dengan read_file sebelum memberi answer final: "
            f"{', '.join(missing_files)}. "
            "Jika lebih dari satu file belum dibaca, gunakan action read_files."
          ),
          "result_meta": "system feedback",
        })
        continue

      if missing_files:
        auto_read_missing_files(
          provider,
          project_path,
          question,
          history,
          missing_files,
          verbose,
        )

      response = synthesize_final_answer(
        provider,
        question,
        project_map,
        history,
        depth,
        intent,
        required_files,
        verbose,
      )

      if verbose:
        elapsed = time.perf_counter() - started_at
        print(f"[agent] Final answer ready in {elapsed:.1f}s")

      return response

    result = run_agent_action(project_path, action)
    result_summary = summarize_tool_result(action, result)
    note = build_observation_note(
      provider,
      question,
      action,
      result_summary,
      result,
      verbose,
    )

    if verbose:
      print(f"[tool] {result_summary}")
      print(f"[memory] note saved ({len(note)} chars)")

    history.append({
      "action": action,
      "result_meta": result_summary,
      "note": note,
    })

  if history:
    missing_files = get_missing_required_files(intent, history, required_files)

    if missing_files:
      auto_read_missing_files(
        provider,
        project_path,
        question,
        history,
        missing_files,
        verbose,
      )

    if verbose:
      print("[agent] Max steps reached; synthesizing final answer from memory notes.")

    return synthesize_final_answer(
      provider,
      question,
      project_map,
      history,
      depth,
      intent,
      required_files,
      verbose,
    )

  raise AgentError(
    f"Agent belum punya observation setelah {effective_max_steps} langkah. "
    "Coba naikkan --max-steps atau pakai pertanyaan yang lebih spesifik."
  )


def resolve_effective_max_steps(
  depth: str,
  required_files: tuple[str, ...],
  explicit_max_steps: int | None,
) -> int:
  if explicit_max_steps:
    return explicit_max_steps

  base_steps = get_depth_max_steps(depth)
  max_auto_steps = get_depth_max_auto_steps(depth)
  needed_steps = len(required_files) + 2

  return min(max(base_steps, needed_steps), max_auto_steps)


def is_generic_reason(reason: str) -> bool:
  reason_text = reason.lower()
  generic_patterns = (
    "membaca file wajib",
    "membaca file utama",
    "memahami struktur",
    "memahami project",
    "memahami proyek",
    "memahami alur kerja dasar",
  )

  return any(pattern in reason_text for pattern in generic_patterns)


def ask_agent_for_action(
  provider,
  prompt: str,
  history: list[dict[str, Any]],
  verbose: bool,
) -> dict[str, Any]:
  retry_feedback = ""

  for attempt in range(1, MAX_AGENT_PARSE_RETRIES + 2):
    raw_response = generate_agent_text(
      provider,
      prompt + retry_feedback,
      num_predict=ACTION_NUM_PREDICT,
      temperature=AGENT_TEMPERATURE,
    )

    try:
      return parse_agent_action(raw_response)
    except AgentError as error:
      if attempt > MAX_AGENT_PARSE_RETRIES:
        raise

      if verbose:
        print(f"[agent] Model returned invalid JSON, retrying ({attempt}/{MAX_AGENT_PARSE_RETRIES})...")

      retry_feedback = (
        "\n\nSYSTEM RETRY FEEDBACK:\n"
        "Respons sebelumnya kosong atau bukan JSON valid. "
        "Balas ulang hanya dengan satu object JSON valid. "
        "Jika file wajib sudah dibaca, gunakan action answer. "
        "Jangan pakai markdown, jangan teks tambahan.\n"
        f"Parse error: {error}\n"
        f"Files already read: {', '.join(get_read_files(history)) or '-'}\n"
      )

  raise AgentError("Agent gagal menghasilkan action JSON valid.")


def build_fallback_action(
  history: list[dict[str, Any]],
  required_files: tuple[str, ...],
) -> dict[str, Any] | None:
  read_files = set(get_read_files(history))
  missing_files = [
    file_path
    for file_path in required_files
    if file_path not in read_files
  ]

  if missing_files:
    files_to_read = missing_files[:MAX_BATCH_READ_FILES]

    if len(files_to_read) == 1:
      return {
        "action": "read_file",
        "path": files_to_read[0],
        "reason": "fallback membaca file strategi karena planner gagal menghasilkan JSON",
      }

    return {
      "action": "read_files",
      "paths": files_to_read,
      "reason": "fallback membaca beberapa file strategi karena planner gagal menghasilkan JSON",
    }

  if history:
    return {
      "action": "answer",
      "reason": "fallback melakukan final synthesis karena planner gagal dan file strategi sudah dibaca",
      "response": "",
    }

  return None


def bootstrap_strategy_files(
  provider,
  project_path: str,
  question: str,
  history: list[dict[str, Any]],
  required_files: tuple[str, ...],
  verbose: bool,
) -> None:
  files_to_read = list(required_files[:MAX_BATCH_READ_FILES])

  if not files_to_read:
    return

  action = {
    "action": "read_files" if len(files_to_read) > 1 else "read_file",
    "reason": (
      "bootstrap membaca file strategi backend utama sebelum planner memilih langkah "
      "berikutnya"
    ),
  }

  if len(files_to_read) > 1:
    action["paths"] = files_to_read
  else:
    action["path"] = files_to_read[0]

  if verbose:
    print(f"[agent bootstrap] Reading strategy files: {', '.join(files_to_read)}")

  append_tool_observation(
    provider,
    project_path,
    question,
    history,
    action,
    verbose,
  )


def summarize_tool_result(action: dict[str, Any], result: str) -> str:
  action_name = action.get("action")
  target = format_action_target(action)
  prefix = f"{action_name} {target}".strip()

  if action_name == "search_code":
    try:
      data = json.loads(result)
      return f"{prefix} -> {len(data)} matches, {len(result)} chars"
    except json.JSONDecodeError:
      return f"{prefix} -> {len(result)} chars"

  if action_name == "list_folder":
    try:
      data = json.loads(result)
      return f"{prefix} -> {len(data)} items, {len(result)} chars"
    except json.JSONDecodeError:
      return f"{prefix} -> {len(result)} chars"

  if action_name == "read_file":
    line_count = len(result.splitlines())
    return f"{prefix} -> {line_count} lines, {len(result)} chars"

  if action_name == "read_files":
    file_count = len(action.get("paths", []))
    line_count = len(result.splitlines())
    return f"{prefix} -> {file_count} files, {line_count} lines, {len(result)} chars"

  if action_name == "outline_file":
    line_count = len(result.splitlines())
    return f"{prefix} -> {line_count} outline lines, {len(result)} chars"

  return f"{prefix} -> {len(result)} chars"


def run_agent_action(project_path: str, action: dict[str, Any]) -> str:
  action_name = action.get("action")

  if action_name == "read_file":
    path = require_text_field(action, "path")
    return read_file(project_path, path)

  if action_name == "read_files":
    paths = require_paths_field(action)
    parts = []

    for path in paths:
      parts.append(
        f"FILE: {path}\n"
        "```text\n"
        f"{read_file(project_path, path)}\n"
        "```"
      )

    return "\n\n".join(parts)

  if action_name == "outline_file":
    path = require_text_field(action, "path")
    return outline_file(project_path, path)

  if action_name == "search_code":
    query = require_text_field(action, "query")
    max_results = int(action.get("max_results", 20))
    results = search_code(project_path, query, max_results=max_results)
    return json.dumps(results, indent=2, ensure_ascii=False)

  if action_name == "list_folder":
    path = action.get("path") or "."
    results = list_folder(project_path, str(path))
    return json.dumps(results, indent=2, ensure_ascii=False)

  raise AgentError(f"Action tidak didukung: {action_name}")


def auto_read_missing_files(
  provider,
  project_path: str,
  question: str,
  history: list[dict[str, Any]],
  missing_files: list[str],
  verbose: bool,
) -> None:
  files_to_read = missing_files[:MAX_BATCH_READ_FILES]

  if not files_to_read:
    return

  action = {
    "action": "read_files" if len(files_to_read) > 1 else "read_file",
    "reason": "auto-read file strategi yang belum sempat dibaca sebelum final synthesis",
  }

  if len(files_to_read) > 1:
    action["paths"] = files_to_read
  else:
    action["path"] = files_to_read[0]

  if verbose:
    print(f"[agent] Auto-reading missing strategy files: {', '.join(files_to_read)}")

  append_tool_observation(
    provider,
    project_path,
    question,
    history,
    action,
    verbose,
  )


def append_tool_observation(
  provider,
  project_path: str,
  question: str,
  history: list[dict[str, Any]],
  action: dict[str, Any],
  verbose: bool,
) -> None:
  result = run_agent_action(project_path, action)
  result_summary = summarize_tool_result(action, result)
  note = build_observation_note(
    provider,
    question,
    action,
    result_summary,
    result,
    verbose,
  )

  if verbose:
    print(f"[tool] {result_summary}")
    print(f"[memory] note saved ({len(note)} chars)")

  history.append({
    "action": action,
    "result_meta": result_summary,
    "note": note,
  })


def format_action_target(action: dict[str, Any]) -> str:
  if action.get("paths"):
    return ", ".join(str(path) for path in action.get("paths", []))

  return str(action.get("path") or action.get("query") or "")


def build_observation_note(
  provider,
  question: str,
  action: dict[str, Any],
  result_summary: str,
  result: str,
  verbose: bool,
) -> str:
  from llm.prompt_templates import build_observation_note_prompt

  prompt = build_observation_note_prompt(
    question,
    action,
    result_summary,
    truncate_text(result, MAX_NOTE_SOURCE_CHARS),
  )
  note = generate_agent_text(
    provider,
    prompt,
    num_predict=NOTE_NUM_PREDICT,
    temperature=AGENT_TEMPERATURE,
  ).strip()

  if note:
    return note

  if verbose:
    print("[memory] Model returned empty note; using fallback note.")

  return build_fallback_observation_note(action, result_summary, result)


def build_fallback_observation_note(
  action: dict[str, Any],
  result_summary: str,
  result: str,
) -> str:
  files = get_observed_files(action, result)
  symbols = extract_python_symbols(result)
  note_lines = [
    f"- {result_summary}",
    "- Catatan fallback: model tidak menghasilkan ringkasan observation, jadi memory dibuat dari metadata tool.",
  ]

  if files:
    note_lines.append(f"- File terbaca: {', '.join(files)}")

  if symbols:
    note_lines.append(f"- Symbol Python terlihat: {', '.join(symbols)}")

  return "\n".join(note_lines)


def get_observed_files(action: dict[str, Any], result: str) -> list[str]:
  files = re.findall(r"^FILE:\s+(.+)$", result, flags=re.MULTILINE)

  if files:
    return files[:MAX_BATCH_READ_FILES]

  if action.get("paths"):
    return [str(path) for path in action.get("paths", [])][:MAX_BATCH_READ_FILES]

  if action.get("path"):
    return [str(action["path"])]

  return []


def extract_python_symbols(result: str, max_symbols: int = 30) -> list[str]:
  symbols = []
  seen = set()
  pattern = re.compile(
    r"^\s*(class|def|async\s+def)\s+([A-Za-z_][A-Za-z0-9_]*)",
    flags=re.MULTILINE,
  )

  for match in pattern.finditer(result):
    symbol_type = "async def" if match.group(1).startswith("async") else match.group(1)
    symbol = f"{symbol_type} {match.group(2)}"

    if symbol in seen:
      continue

    seen.add(symbol)
    symbols.append(symbol)

    if len(symbols) >= max_symbols:
      break

  return symbols


def synthesize_final_answer(
  provider,
  question: str,
  project_map: str,
  history: list[dict[str, Any]],
  depth: str,
  intent: str,
  required_files: tuple[str, ...],
  verbose: bool = False,
) -> str:
  from llm.prompt_templates import build_final_synthesis_prompt

  if verbose:
    print("[agent] Synthesizing final answer from memory notes...")

  prompt = build_final_synthesis_prompt(
    question,
    project_map,
    history,
    depth,
    intent,
    required_files,
  )
  response = generate_final_response(provider, prompt).strip()

  if not response:
    raise AgentError("Final synthesis menghasilkan response kosong.")

  return response


def generate_final_response(provider, prompt: str) -> str:
  if hasattr(provider, "generate_stream"):
    chunks = []

    try:
      stream = provider.generate_stream(
        prompt,
        num_predict=FINAL_NUM_PREDICT,
        temperature=AGENT_TEMPERATURE,
      )
    except TypeError:
      stream = provider.generate_stream(prompt)

    for chunk in stream:
      chunks.append(chunk)

    return "".join(chunks)

  return generate_agent_text(
    provider,
    prompt,
    num_predict=FINAL_NUM_PREDICT,
    temperature=AGENT_TEMPERATURE,
  )


def generate_agent_text(
  provider,
  prompt: str,
  num_predict: int,
  temperature: float,
) -> str:
  try:
    return provider.generate(
      prompt,
      num_predict=num_predict,
      temperature=temperature,
    )
  except TypeError:
    return provider.generate(prompt)


def parse_agent_action(raw_response: str) -> dict[str, Any]:
  text = strip_code_fence(raw_response.strip())

  if not text:
    raise AgentError("Agent mengirim response kosong.")

  try:
    data = json.loads(text)
  except json.JSONDecodeError:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if not match:
      raise AgentError(f"Agent tidak mengirim JSON valid:\n{raw_response}")

    data = json.loads(match.group(0))

  if not isinstance(data, dict):
    raise AgentError("Agent JSON harus berupa object.")

  if "action" not in data:
    raise AgentError("Agent JSON wajib punya field action.")

  return data


def get_read_files(history: list[dict[str, Any]]) -> list[str]:
  read_files = []

  for item in history:
    action = item.get("action", {})
    action_name = action.get("action")

    if action_name == "read_file":
      read_files.append(str(action.get("path", "")).replace("\\", "/"))

    if action_name == "read_files":
      read_files.extend(
        str(path).replace("\\", "/")
        for path in action.get("paths", [])
      )

  return read_files


def strip_code_fence(text: str) -> str:
  if not text.startswith("```"):
    return text

  lines = text.splitlines()

  if len(lines) >= 3 and lines[-1].strip() == "```":
    return "\n".join(lines[1:-1]).strip()

  return text


def require_text_field(data: dict[str, Any], field_name: str) -> str:
  value = data.get(field_name)

  if not isinstance(value, str) or not value.strip():
    raise AgentError(f"Action wajib punya field string: {field_name}")

  return value


def require_paths_field(data: dict[str, Any]) -> list[str]:
  paths = data.get("paths")

  if not isinstance(paths, list) or not paths:
    raise AgentError("Action read_files wajib punya field paths berupa list string.")

  clean_paths = []

  for path in paths:
    if not isinstance(path, str) or not path.strip():
      raise AgentError("Semua item paths harus string non-empty.")

    clean_paths.append(path)

  if len(clean_paths) > MAX_BATCH_READ_FILES:
    raise AgentError(
      f"Action read_files maksimal {MAX_BATCH_READ_FILES} file per langkah."
    )

  return clean_paths


def truncate_text(text: str, max_chars: int) -> str:
  if len(text) <= max_chars:
    return text

  omitted = len(text) - max_chars
  return f"{text[:max_chars]}\n\n... omitted {omitted} characters ..."


def should_delay_answer(
  intent: str,
  missing_files: list[str],
  step_number: int,
  max_steps: int,
) -> bool:
  if step_number >= max_steps:
    return False

  if not requires_required_files(intent):
    return False

  return bool(missing_files)


def get_missing_required_files(
  intent: str,
  history: list[dict[str, Any]],
  required_files: tuple[str, ...],
) -> list[str]:
  if not requires_required_files(intent):
    return []

  read_files = set(get_read_files(history))

  return [
    file_path
    for file_path in required_files
    if file_path not in read_files
  ]
