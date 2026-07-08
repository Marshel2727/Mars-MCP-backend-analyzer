from core.project_scanner import scan_project
from tools.read_file import read_file


def search_code(project_path: str, keyword: str, max_results: int = 50) -> list[dict]:
  results: list[dict] = []

  if not keyword.strip():
    return results

  if max_results <= 0:
    return results

  keyword_lower = keyword.lower()
  files = scan_project(project_path)

  for file_path in files:
    try:
      content = read_file(project_path, str(file_path))
    except Exception:
      continue

    lines = content.splitlines()

    for line_number, line in enumerate(lines, start=1):
      if keyword_lower not in line.lower():
        continue

      results.append({
        "file": str(file_path),
        "line": line_number,
        "text": line.strip(),
      })

      if len(results) >= max_results:
        return results

  return results