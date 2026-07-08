import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.project_map import extract_file_symbols
from core.project_scanner import scan_project
from tools.search_code import search_code


STOP_WORDS = {
  "ada",
  "agar",
  "akan",
  "apa",
  "atau",
  "audit",
  "bagaimana",
  "bisa",
  "bug",
  "code",
  "dan",
  "dari",
  "dengan",
  "error",
  "file",
  "fix",
  "folder",
  "gagal",
  "ini",
  "itu",
  "jelaskan",
  "kalo",
  "kalau",
  "kode",
  "mana",
  "pada",
  "perbaiki",
  "project",
  "review",
  "saja",
  "saya",
  "struktur",
  "the",
  "untuk",
  "yang",
}


ROLE_HINTS = {
  "model": ("models/", "schema", "entity", "database", "db", "migration"),
  "models": ("models/", "schema", "entity", "database", "db", "migration"),
  "route": ("routes/", "routers/", "controller", "endpoint", "api/"),
  "routes": ("routes/", "routers/", "controller", "endpoint", "api/"),
  "service": ("services/", "service", "business", "usecase"),
  "services": ("services/", "service", "business", "usecase"),
  "config": ("config", "settings", ".env", "docker", "requirements"),
  "database": ("models/", "database", "db", "migration", "alembic"),
  "auth": ("auth", "security", "jwt", "login", "user"),
  "payment": ("payment", "pembayaran", "order", "transaction"),
  "upload": ("upload", "gallery", "image", "gambar"),
}


def find_relevant_files(
  project_path: str,
  question: str,
  max_files: int = 8,
  max_symbols: int = 6,
) -> list[dict[str, Any]]:
  if max_files <= 0:
    return []

  max_symbols = max(0, min(max_symbols, 20))
  terms = extract_search_terms(question)
  source_focused = is_source_focused_question(question)
  files = [str(file_path).replace("\\", "/") for file_path in scan_project(project_path)]
  scores: defaultdict[str, int] = defaultdict(int)
  reasons: defaultdict[str, list[str]] = defaultdict(list)

  for file_path in files:
    score_file_type(file_path, source_focused, scores, reasons)
    score_path_matches(file_path, terms, scores, reasons)
    score_role_hints(file_path, terms, scores, reasons)

  for term in terms[:8]:
    for match in search_code(project_path, term, max_results=max(max_files * 8, 1)):
      file_path = str(match["file"]).replace("\\", "/")
      scores[file_path] += 2
      append_reason(reasons[file_path], f"contains `{term}` at line {match['line']}")

  ranked_files = sorted(
    scores,
    key=lambda file_path: (
      -scores[file_path],
      -source_rank(file_path, source_focused),
      file_path.count("/"),
      file_path,
    ),
  )

  results = []

  for file_path in ranked_files[:max_files]:
    symbols = extract_file_symbols(
      project_path,
      file_path,
      max_symbols=max_symbols,
    )
    results.append({
      "file": file_path,
      "score": scores[file_path],
      "reasons": reasons[file_path][:4],
      "symbols": symbols,
    })

  return results


def extract_search_terms(question: str) -> list[str]:
  words = re.findall(r"[a-zA-Z0-9_./-]+", question.lower())
  terms = []
  seen = set()

  for word in words:
    if len(word) < 3:
      continue

    if word in STOP_WORDS:
      continue

    if word in seen:
      continue

    seen.add(word)
    terms.append(word)

  return terms


def is_source_focused_question(question: str) -> bool:
  question_text = question.lower()
  source_words = (
    "bug",
    "error",
    "review",
    "risiko",
    "behavior",
    "kode",
    "code",
    "fungsi",
    "function",
    "class",
    "method",
    "implementasi",
  )
  docs_words = ("docs", "dokumentasi", "readme", "panduan")

  if any(word in question_text for word in docs_words):
    return False

  return any(word in question_text for word in source_words)


def score_file_type(
  file_path: str,
  source_focused: bool,
  scores: defaultdict[str, int],
  reasons: defaultdict[str, list[str]],
) -> None:
  suffix = Path(file_path).suffix.lower()

  if not source_focused:
    return

  if suffix == ".py":
    scores[file_path] += 6
    append_reason(reasons[file_path], "source file boost")
    return

  if suffix in {".md", ".txt"}:
    scores[file_path] -= 4
    append_reason(reasons[file_path], "documentation penalty for source-focused query")


def source_rank(file_path: str, source_focused: bool) -> int:
  if not source_focused:
    return 0

  suffix = Path(file_path).suffix.lower()

  if suffix == ".py":
    return 2

  if suffix in {".ps1", ".bat", ".cmd", ".sh"}:
    return 1

  return 0


def score_path_matches(
  file_path: str,
  terms: list[str],
  scores: defaultdict[str, int],
  reasons: defaultdict[str, list[str]],
) -> None:
  lower_path = file_path.lower()
  stem = Path(file_path).stem.lower()

  for term in terms:
    if term in lower_path:
      scores[file_path] += 8
      append_reason(reasons[file_path], f"path matches `{term}`")

    if term == stem:
      scores[file_path] += 10
      append_reason(reasons[file_path], f"filename matches `{term}`")


def score_role_hints(
  file_path: str,
  terms: list[str],
  scores: defaultdict[str, int],
  reasons: defaultdict[str, list[str]],
) -> None:
  lower_path = file_path.lower()

  for term in terms:
    hints = ROLE_HINTS.get(term)

    if not hints:
      continue

    for hint in hints:
      if hint in lower_path:
        scores[file_path] += 6
        append_reason(reasons[file_path], f"role hint `{term}` matches `{hint}`")
        break


def append_reason(reasons: list[str], reason: str) -> None:
  if reason not in reasons:
    reasons.append(reason)
