from pathlib import Path
from typing import Any

from core.project_brief import build_project_brief
from core.relevance import extract_search_terms, find_relevant_files


DEPTH_SETTINGS = {
  "quick": {
    "max_files_per_layer": 3,
    "max_symbols": 3,
    "max_relevant_files": 5,
    "max_outline_files": 2,
    "line_budget": 80,
  },
  "normal": {
    "max_files_per_layer": 5,
    "max_symbols": 4,
    "max_relevant_files": 8,
    "max_outline_files": 4,
    "line_budget": 120,
  },
  "deep": {
    "max_files_per_layer": 8,
    "max_symbols": 6,
    "max_relevant_files": 12,
    "max_outline_files": 7,
    "line_budget": 180,
  },
}


def build_task_plan(
  project_path: str,
  question: str,
  depth: str = "normal",
) -> dict[str, Any]:
  depth = normalize_depth(depth)
  settings = DEPTH_SETTINGS[depth]
  intent = detect_plan_intent(question)
  brief = build_project_brief(
    project_path,
    max_files_per_layer=settings["max_files_per_layer"],
    max_symbols=settings["max_symbols"],
  )
  relevant_files = find_relevant_files(
    project_path,
    question,
    max_files=settings["max_relevant_files"],
    max_symbols=settings["max_symbols"],
  )
  candidate_files = select_candidate_files(brief, relevant_files, intent)
  outline_files = [
    file_path
    for file_path in candidate_files
    if is_source_file(file_path)
  ][:settings["max_outline_files"]]

  return {
    "goal": build_goal(question, intent),
    "intent": intent,
    "depth": depth,
    "execution_policy": {
      "mode": "plan_only",
      "read_only": True,
      "prefer_line_reads": True,
      "avoid_full_file_reads_until_needed": True,
    },
    "project": {
      "type": brief["project_type"],
      "total_files": brief["total_files"],
      "top_folders": brief["top_folders"],
    },
    "candidate_files": candidate_files,
    "relevant_files": relevant_files,
    "allowed_tools": [
      "mars_project_brief",
      "mars_find_relevant_files",
      "mars_search_code",
      "mars_outline_file",
      "mars_read_lines",
      "mars_read_file",
    ],
    "steps": build_steps(
      project_path,
      question,
      intent,
      settings,
      outline_files,
    ),
    "stop_condition": build_stop_condition(intent),
    "final_answer_guidance": build_final_answer_guidance(intent),
  }


def normalize_depth(depth: str) -> str:
  if depth in DEPTH_SETTINGS:
    return depth

  return "normal"


def detect_plan_intent(question: str) -> str:
  text = question.lower()

  if contains_any(text, ("alur kerja", "workflow", "cara kerja", "flow", "end-to-end")):
    return "workflow"

  if contains_any(text, ("bug", "error", "gagal", "traceback", "exception", "kenapa", "tidak jalan")):
    return "debug"

  if contains_any(text, ("model", "models", "schema", "database", "db", "tabel")):
    return "models"

  if contains_any(text, ("improve", "impruv", "tingkatkan", "perbaiki", "review", "audit", "risiko", "refactor")):
    return "review"

  if contains_any(text, ("struktur", "analisis project", "analisa project", "overview", "ringkasan")):
    return "overview"

  return "general"


def contains_any(text: str, words: tuple[str, ...]) -> bool:
  return any(word in text for word in words)


def build_goal(question: str, intent: str) -> str:
  intent_goals = {
    "workflow": "Menjelaskan alur kerja backend end-to-end berdasarkan file penting.",
    "debug": "Menemukan penyebab masalah dengan membaca bukti kode yang relevan.",
    "models": "Memahami layer model/schema/database dan relasinya dengan backend.",
    "review": "Mengidentifikasi improvement, risiko desain, dan gap verifikasi yang actionable.",
    "overview": "Memberi gambaran struktur dan komponen utama project backend.",
    "general": "Menjawab pertanyaan user dengan konteks backend yang paling relevan.",
  }

  return intent_goals.get(intent, intent_goals["general"]) + f" Request: {question}"


def select_candidate_files(
  brief: dict[str, Any],
  relevant_files: list[dict[str, Any]],
  intent: str,
) -> list[str]:
  selected: list[str] = []

  for file_info in brief.get("entrypoints", []):
    append_unique(selected, file_info["file"])

  if intent in {"debug", "review"}:
    for file_info in relevant_files:
      append_unique(selected, file_info["file"])

  for layer in layer_priority(intent):
    for file_info in brief.get("layers", {}).get(layer, []):
      append_unique(selected, file_info["file"])

  for file_info in relevant_files:
    append_unique(selected, file_info["file"])

  for file_path in brief.get("suggested_next_files", []):
    append_unique(selected, file_path)

  return selected[:14]


def layer_priority(intent: str) -> tuple[str, ...]:
  if intent == "workflow":
    return ("routes", "services", "models", "cli", "mcp", "core", "config", "tools")

  if intent == "debug":
    return ("routes", "services", "models", "core", "config")

  if intent == "models":
    return ("models", "services", "routes", "config", "core")

  if intent == "review":
    return ("mcp", "cli", "core", "tools", "config", "llm")

  return ("routes", "services", "models", "core", "config", "mcp", "cli", "tools")


def build_steps(
  project_path: str,
  question: str,
  intent: str,
  settings: dict[str, int],
  outline_files: list[str],
) -> list[dict[str, Any]]:
  steps = [
    {
      "id": 1,
      "tool": "mars_project_brief",
      "args": {
        "project_path": project_path,
        "max_files_per_layer": settings["max_files_per_layer"],
        "max_symbols": settings["max_symbols"],
      },
      "reason": "Mendapatkan struktur kecil project sebelum membaca file spesifik.",
    },
    {
      "id": 2,
      "tool": "mars_find_relevant_files",
      "args": {
        "project_path": project_path,
        "question": question,
        "max_files": settings["max_relevant_files"],
        "max_symbols": settings["max_symbols"],
      },
      "reason": "Memilih file yang paling relevan dengan request user.",
    },
  ]

  next_id = 3

  if intent in {"debug", "review"}:
    for term in extract_search_terms(question)[:3]:
      steps.append({
        "id": next_id,
        "tool": "mars_search_code",
        "args": {
          "project_path": project_path,
          "query": term,
          "max_results": 20,
        },
        "reason": f"Mencari bukti kode yang mengandung keyword `{term}`.",
      })
      next_id += 1

  for file_path in outline_files:
    steps.append({
      "id": next_id,
      "tool": "mars_outline_file",
      "args": {
        "project_path": project_path,
        "file_path": file_path,
      },
      "reason": "Melihat struktur file sebelum membaca isi detail.",
    })
    next_id += 1

  for file_path in outline_files[:2]:
    reason = "Membaca bagian awal file kandidat untuk menangkap setup, import, dan alur utama."
    steps.append({
      "id": next_id,
      "tool": "mars_read_lines",
      "args": {
        "project_path": project_path,
        "file_path": file_path,
        "start_line": 1,
        "end_line": settings["line_budget"],
        "max_lines": settings["line_budget"],
        "reason": reason,
      },
      "reason": reason,
    })
    next_id += 1

  steps.append({
    "id": next_id,
    "tool": "assistant_synthesize",
    "args": {
      "question": question,
      "use": [
        "project brief",
        "relevant files",
        "outlines",
        "selected line reads",
      ],
    },
    "reason": "Menyusun jawaban akhir dari observasi ringkas, bukan dari dump full code.",
  })

  return steps


def build_stop_condition(intent: str) -> str:
  if intent == "workflow":
    return "Berhenti setelah entrypoint, routing/API, service/business logic, model/database, dan output response sudah terhubung."

  if intent == "debug":
    return "Berhenti setelah ada penyebab paling mungkin, bukti kode, dan langkah verifikasi."

  if intent == "models":
    return "Berhenti setelah model/schema utama, relasi data, dan pemakaiannya di service/route sudah jelas."

  if intent == "review":
    return "Berhenti setelah findings actionable, risiko, file terkait, dan rekomendasi prioritas sudah cukup."

  return "Berhenti setelah file utama dan hubungan komponennya cukup untuk menjawab request user."


def build_final_answer_guidance(intent: str) -> list[str]:
  formats = {
    "workflow": [
      "## Ringkasan Alur",
      "## Alur End-to-End",
      "## Peran Komponen",
      "## File yang Dicek",
      "## Batasan Analisis",
    ],
    "debug": [
      "## Ringkasan Masalah",
      "## Kemungkinan Penyebab",
      "## Bukti Kode",
      "## Cara Verifikasi",
      "## Rekomendasi Fix",
    ],
    "models": [
      "## Ringkasan Models",
      "## Struktur Data",
      "## Relasi dan Pemakaian",
      "## Risiko",
      "## File yang Dicek",
    ],
    "review": [
      "## Findings",
      "## Risiko Desain",
      "## Rekomendasi Prioritas",
      "## File yang Dicek",
      "## Test Gap",
    ],
  }

  return formats.get(intent, [
    "## Ringkasan",
    "## Detail",
    "## File yang Dicek",
    "## Rekomendasi",
  ])


def is_source_file(file_path: str) -> bool:
  return Path(file_path).suffix.lower() in {".py", ".js", ".ts"}


def append_unique(items: list[str], item: str) -> None:
  if item not in items:
    items.append(item)
