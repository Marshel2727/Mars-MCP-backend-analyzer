from collections import Counter
from pathlib import Path
from typing import Any

from core.project_map import extract_file_symbols
from core.project_scanner import scan_project


ENTRYPOINT_NAMES = {
  "main.py",
  "app.py",
  "run.py",
  "server.py",
  "manage.py",
  "wsgi.py",
  "asgi.py",
}

IMPORTANT_FILE_NAMES = {
  "requirements.txt",
  "pyproject.toml",
  "Dockerfile",
  "docker-compose.yml",
  "docker-compose.yaml",
  ".env.example",
}

LAYER_PATTERNS = {
  "cli": ("cli.py", "commands/", "command"),
  "mcp": ("mcp", "mcp_server", "mars_mcp_server.py"),
  "config": ("config/", "settings.py", "config.py", ".env", "docker"),
  "routes": ("routes/", "routers/", "controllers/", "api/", "endpoints/"),
  "services": ("services/", "service/", "usecases/", "use_cases/"),
  "models": ("models/", "schemas/", "entities/", "dto/"),
  "core": ("core/", "domain/", "lib/"),
  "llm": ("llm/", "prompt", "provider", "ollama", "openai"),
  "tools": ("tools/", "utils/"),
  "tests": ("tests/", "test_"),
}


def build_project_brief(
  project_path: str,
  max_files_per_layer: int = 5,
  max_symbols: int = 4,
) -> dict[str, Any]:
  max_files_per_layer = clamp_int(max_files_per_layer, minimum=1, maximum=20)
  max_symbols = clamp_int(max_symbols, minimum=0, maximum=20)
  files = [str(file_path).replace("\\", "/") for file_path in scan_project(project_path)]
  folder_counts = count_top_folders(files)
  layers = group_files_by_layer(files, max_files_per_layer)
  entrypoints = find_entrypoints(files)
  important_files = find_important_files(files)
  project_type = detect_project_type(files, layers)
  suggested_files = select_suggested_files(entrypoints, important_files, layers)

  return {
    "project_type": project_type,
    "total_files": len(files),
    "top_folders": folder_counts,
    "entrypoints": annotate_files(project_path, entrypoints, max_symbols),
    "important_files": annotate_files(project_path, important_files, max_symbols),
    "layers": {
      layer: annotate_files(project_path, layer_files, max_symbols)
      for layer, layer_files in layers.items()
      if layer_files
    },
    "suggested_next_files": suggested_files[:10],
  }


def count_top_folders(files: list[str]) -> dict[str, int]:
  counts = Counter(
    file_path.split("/", 1)[0]
    for file_path in files
    if "/" in file_path
  )

  return dict(counts.most_common(12))


def group_files_by_layer(
  files: list[str],
  max_files_per_layer: int,
) -> dict[str, list[str]]:
  layers: dict[str, list[str]] = {layer: [] for layer in LAYER_PATTERNS}

  for file_path in files:
    lower_path = file_path.lower()

    for layer, patterns in LAYER_PATTERNS.items():
      if any(pattern in lower_path for pattern in patterns):
        layers[layer].append(file_path)
        break

  for layer, layer_files in layers.items():
    layer_files.sort(key=layer_file_sort_key)
    layers[layer] = layer_files[:max_files_per_layer]

  return layers


def find_entrypoints(files: list[str]) -> list[str]:
  entrypoints = []

  for file_path in files:
    if Path(file_path).name in ENTRYPOINT_NAMES:
      entrypoints.append(file_path)

  return entrypoints[:8]


def find_important_files(files: list[str]) -> list[str]:
  important_files = []

  for file_path in files:
    if Path(file_path).name in IMPORTANT_FILE_NAMES:
      important_files.append(file_path)

  return important_files[:8]


def detect_project_type(files: list[str], layers: dict[str, list[str]]) -> str:
  lower_files = [file_path.lower() for file_path in files]

  if has_mcp_files(lower_files):
    return "python cli/mcp developer tool"

  if layers.get("routes") and layers.get("services"):
    return "python backend service"

  if any(file_path.endswith("manage.py") for file_path in lower_files):
    return "python django backend"

  if layers.get("cli"):
    return "python cli tool"

  return "python project"


def select_suggested_files(
  entrypoints: list[str],
  important_files: list[str],
  layers: dict[str, list[str]],
) -> list[str]:
  selected = []

  for file_path in entrypoints + important_files:
    append_unique(selected, file_path)

  for layer in ("cli", "mcp", "config", "routes", "services", "models", "core", "llm", "tools"):
    for file_path in layers.get(layer, [])[:2]:
      append_unique(selected, file_path)

  return selected


def annotate_files(
  project_path: str,
  files: list[str],
  max_symbols: int,
) -> list[dict[str, Any]]:
  annotated_files = []

  for file_path in files:
    annotated_files.append({
      "file": file_path,
      "symbols": extract_file_symbols(project_path, file_path, max_symbols=max_symbols),
    })

  return annotated_files


def append_unique(items: list[str], item: str) -> None:
  if item not in items:
    items.append(item)


def layer_file_sort_key(file_path: str) -> tuple[int, int, str]:
  suffix = Path(file_path).suffix.lower()

  if suffix == ".py":
    priority = 0
  elif suffix in {".ps1", ".bat", ".cmd", ".sh"}:
    priority = 2
  elif suffix in {".md", ".txt"}:
    priority = 3
  else:
    priority = 1

  return (priority, file_path.count("/"), file_path)


def has_mcp_files(lower_files: list[str]) -> bool:
  for file_path in lower_files:
    file_name = Path(file_path).name

    if file_name == "mars_mcp_server.py":
      return True

    if file_name.startswith("mcp_") or file_name.endswith("_mcp.py"):
      return True

    if "/mcp/" in file_path:
      return True

  return False


def clamp_int(value: int, minimum: int, maximum: int) -> int:
  return max(minimum, min(value, maximum))
