import ast
import re
from pathlib import Path

from tools.read_file import read_file


JS_SYMBOL_PATTERNS = (
  re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("),
  re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b"),
  re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
  ),
)


def outline_file(project_path: str, file_path: str) -> str:
  suffix = Path(file_path).suffix.lower()

  if suffix == ".py":
    return outline_python_file(project_path, file_path)

  if suffix in {".js", ".jsx", ".ts", ".tsx"}:
    return outline_js_file(project_path, file_path)

  return f"{file_path}: outline tidak tersedia untuk ekstensi {suffix or '(none)'}."


def outline_python_file(project_path: str, file_path: str) -> str:
  content = read_file(project_path, file_path)

  try:
    tree = ast.parse(content)
  except SyntaxError as error:
    return f"{file_path}: gagal parse Python: {error}"

  lines = [f"OUTLINE: {file_path}"]

  for node in tree.body:
    if isinstance(node, ast.ClassDef):
      lines.append(f"- line {node.lineno}: class {node.name}")

      for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
          lines.append(f"  - line {child.lineno}: {node.name}.{child.name}()")

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
      lines.append(f"- line {node.lineno}: {node.name}()")

  if len(lines) == 1:
    lines.append("- Tidak ada class/function top-level yang ditemukan.")

  return "\n".join(lines)


def outline_js_file(project_path: str, file_path: str) -> str:
  content = read_file(project_path, file_path)
  lines = [f"OUTLINE: {file_path}"]

  for line_number, line in enumerate(content.splitlines(), start=1):
    for pattern in JS_SYMBOL_PATTERNS:
      match = pattern.match(line)

      if not match:
        continue

      lines.append(f"- line {line_number}: {match.group(1)}")
      break

  if len(lines) == 1:
    lines.append("- Tidak ada simbol JS/TS top-level yang ditemukan.")

  return "\n".join(lines)
