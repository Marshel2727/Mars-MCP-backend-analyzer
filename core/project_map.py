import ast
import re
from pathlib import Path

from core.project_scanner import scan_project
from tools.read_file import read_file


DEFAULT_MAX_FILES = 200
DEFAULT_MAX_SYMBOLS_PER_FILE = 12


JS_SYMBOL_PATTERNS = (
  re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("),
  re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b"),
  re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
  ),
)


def build_project_map(
  project_path: str,
  max_files: int = DEFAULT_MAX_FILES,
  max_symbols_per_file: int = DEFAULT_MAX_SYMBOLS_PER_FILE,
) -> str:
  files = scan_project(project_path)
  shown_files = files[:max_files]
  lines = [
    "PROJECT MAP",
    f"Total files: {len(files)}",
    f"Files shown: {len(shown_files)}",
    "",
  ]

  for file_path in shown_files:
    file_path_text = str(file_path)
    symbols = extract_file_symbols(
      project_path,
      file_path_text,
      max_symbols=max_symbols_per_file,
    )

    lines.append(f"- {file_path_text}")

    if symbols:
      lines.append(f"  symbols: {', '.join(symbols)}")

  if len(files) > max_files:
    lines.extend([
      "",
      f"... {len(files) - max_files} more files omitted from project map.",
    ])

  return "\n".join(lines)


def extract_file_symbols(
  project_path: str,
  file_path: str,
  max_symbols: int = DEFAULT_MAX_SYMBOLS_PER_FILE,
) -> list[str]:
  suffix = Path(file_path).suffix.lower()

  if suffix == ".py":
    return extract_python_symbols(project_path, file_path, max_symbols)

  if suffix in {".js", ".jsx", ".ts", ".tsx"}:
    return extract_js_symbols(project_path, file_path, max_symbols)

  return []


def extract_python_symbols(
  project_path: str,
  file_path: str,
  max_symbols: int,
) -> list[str]:
  try:
    content = read_file(project_path, file_path)
    tree = ast.parse(content)
  except Exception:
    return []

  symbols = []

  for node in tree.body:
    if isinstance(node, ast.ClassDef):
      symbols.append(f"class {node.name}")

      for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
          symbols.append(f"{node.name}.{child.name}()")

          if len(symbols) >= max_symbols:
            return symbols

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
      symbols.append(f"{node.name}()")

    if len(symbols) >= max_symbols:
      return symbols

  return symbols


def extract_js_symbols(
  project_path: str,
  file_path: str,
  max_symbols: int,
) -> list[str]:
  try:
    content = read_file(project_path, file_path)
  except Exception:
    return []

  symbols = []

  for line in content.splitlines():
    for pattern in JS_SYMBOL_PATTERNS:
      match = pattern.match(line)

      if not match:
        continue

      symbols.append(match.group(1))

      if len(symbols) >= max_symbols:
        return symbols

      break

  return symbols
