from pathlib import Path

from core.ignore import IgnoreRules


def list_folder(project_path: str, folder_path: str = ".") -> list[dict]:
  root = Path(project_path).resolve()
  target_folder = (root / folder_path).resolve()

  if not root.exists():
    raise FileNotFoundError(f"Folder project tidak ditemukan: {root}")

  if not root.is_dir():
    raise NotADirectoryError(f"Path project bukan folder: {root}")

  if not target_folder.exists():
    raise FileNotFoundError(f"Folder tidak ditemukan: {target_folder}")

  if not target_folder.is_dir():
    raise NotADirectoryError(f"Path bukan folder: {target_folder}")

  try:
    target_folder.relative_to(root)
  except ValueError:
    raise PermissionError("Folder berada di luar folder project.")

  ignore_rules = IgnoreRules()
  if ignore_rules.should_ignore(target_folder):
    raise PermissionError(f"Folder diabaikan oleh ignore rules: {folder_path}")
  results: list[dict] = []

  for item in sorted(target_folder.iterdir()):
    if ignore_rules.should_ignore(item):
      continue

    results.append({
      "name": item.name,
      "path": str(item.relative_to(root)),
      "type": "dir" if item.is_dir() else "file",
    })

  return results
