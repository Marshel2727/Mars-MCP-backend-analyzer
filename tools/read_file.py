from pathlib import Path

from config.settings import MAX_FILE_SIZE
from core.ignore import IgnoreRules


def read_file(project_path: str, file_path: str) -> str:
  root = Path(project_path).resolve()
  target_file = (root / file_path).resolve()

  if not root.exists():
    raise FileNotFoundError(f"Folder tidak ditemukan: {root}")

  if not root.is_dir():
    raise NotADirectoryError(f"Path project bukan folder: {root}")

  if not target_file.exists():
    raise FileNotFoundError(f"File tidak ditemukan: {target_file}")

  if not target_file.is_file():
    raise IsADirectoryError(f"Path bukan file: {target_file}")

  try:
    target_file.relative_to(root)
  except ValueError:
    raise PermissionError("File berada di luar folder project.")

  ignore_rules = IgnoreRules()

  if ignore_rules.should_ignore(target_file):
    raise PermissionError(f"File diabaikan oleh ignore rules: {file_path}")

  if target_file.stat().st_size > MAX_FILE_SIZE:
    raise ValueError(f"File terlalu besar: {file_path}")

  return target_file.read_text(encoding="utf-8", errors="replace")