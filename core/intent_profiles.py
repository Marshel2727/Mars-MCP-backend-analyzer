import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import APP_ROOT
from core.project_scanner import scan_project


PROFILE_PATH = APP_ROOT / "config" / "agent_intent_profiles.json"
DEFAULT_INTENT = "overview"
DEFAULT_DEPTH = "normal"


@lru_cache(maxsize=1)
def load_agent_profiles() -> dict[str, Any]:
  with PROFILE_PATH.open("r", encoding="utf-8") as profile_file:
    return json.load(profile_file)


def detect_agent_intent(question: str) -> str:
  question_text = question.lower()
  profiles = load_agent_profiles().get("intents", {})
  best_intent = DEFAULT_INTENT
  best_score = (0, -1)

  for intent, profile in profiles.items():
    keywords = profile.get("keywords", [])
    match_count = sum(1 for keyword in keywords if keyword.lower() in question_text)
    priority = int(profile.get("priority", 0))
    score = (match_count, priority)

    if score > best_score:
      best_intent = intent
      best_score = score

  if best_score[0] == 0:
    return DEFAULT_INTENT

  return best_intent


def get_intent_profile(intent: str) -> dict[str, Any]:
  profiles = load_agent_profiles().get("intents", {})

  return profiles.get(intent) or profiles[DEFAULT_INTENT]


def get_depth_max_steps(depth: str) -> int:
  depth_profiles = load_agent_profiles().get("depth_profiles", {})
  profile = depth_profiles.get(depth) or depth_profiles[DEFAULT_DEPTH]

  return int(profile["max_steps"])


def get_depth_max_auto_steps(depth: str) -> int:
  depth_profiles = load_agent_profiles().get("depth_profiles", {})
  profile = depth_profiles.get(depth) or depth_profiles[DEFAULT_DEPTH]

  return int(profile.get("max_auto_steps", profile["max_steps"]))


def get_file_strategy(intent: str, depth: str) -> tuple[str, ...]:
  profile = get_intent_profile(intent)
  strategies = profile.get("file_strategy", {})
  roles = strategies.get(depth) or strategies.get(DEFAULT_DEPTH) or []

  return tuple(roles)


def resolve_required_files(project_path: str, intent: str, depth: str) -> tuple[str, ...]:
  roles = get_file_strategy(intent, depth)

  if not roles:
    return ()

  project_files = [str(file).replace("\\", "/") for file in scan_project(project_path)]
  selected_files: list[str] = []

  for role in roles:
    match = find_best_file_for_role(project_files, role, excluded_files=selected_files)

    if match and match not in selected_files:
      selected_files.append(match)

  return tuple(selected_files)


def find_best_file_for_role(
  project_files: list[str],
  role: str,
  excluded_files: list[str] | None = None,
) -> str | None:
  patterns = load_agent_profiles().get("file_role_patterns", {}).get(role, [])
  excluded = set(excluded_files or [])

  if not patterns:
    return None

  scored_files = []

  for file_path in project_files:
    if file_path in excluded:
      continue

    score = score_file_for_patterns(file_path, patterns)

    if score > 0:
      scored_files.append((score, len(file_path), file_path))

  if not scored_files:
    return None

  scored_files.sort(key=lambda item: (-item[0], item[1], item[2]))

  return scored_files[0][2]


def score_file_for_patterns(file_path: str, patterns: list[str]) -> int:
  normalized_file = file_path.lower()
  score = 0

  for pattern in patterns:
    normalized_pattern = pattern.lower()

    if normalized_pattern.endswith("/") and normalized_pattern in normalized_file:
      score += 20
      continue

    if normalized_file == normalized_pattern:
      score += 100
      continue

    if normalized_file.endswith(f"/{normalized_pattern}"):
      score += 90
      continue

    if normalized_pattern in normalized_file:
      score += 40

  return score


def requires_required_files(intent: str) -> bool:
  return bool(get_intent_profile(intent).get("requires_required_files", False))


def get_intent_focus(intent: str) -> str:
  return str(get_intent_profile(intent).get("focus", "Jawab sesuai pertanyaan user."))


def get_final_format(intent: str) -> str:
  sections = get_intent_profile(intent).get("final_format", [])

  if not sections:
    sections = get_intent_profile(DEFAULT_INTENT).get("final_format", [])

  return "\n".join(str(section) for section in sections)


def get_available_depths() -> tuple[str, ...]:
  return tuple(load_agent_profiles().get("depth_profiles", {}).keys())


def get_available_intents() -> tuple[str, ...]:
  return tuple(load_agent_profiles().get("intents", {}).keys())
