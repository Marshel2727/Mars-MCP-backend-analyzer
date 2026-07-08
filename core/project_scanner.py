import os
from pathlib import Path

from config.settings import ALLOWED_EXTENSIONS, ALLOWED_FILENAMES, MAX_FILE_SIZE
from core.ignore import IgnoreRules


def scan_project(project_path: str = ".") -> list[Path]:
  root = Path(project_path).resolve()
  
  if not root.exists():
    raise FileNotFoundError(f"Folder tidak ditemukan: {root}")
  
  if not root.is_dir():
    raise NotADirectoryError(f"Path bukan folder: {root}")
  
  ignore_rules = IgnoreRules()
  
  result: list[Path] = []
  
  for current_dir, dirnames, filenames in os.walk(root):
    current_path = Path(current_dir)
    
    dirnames[:] = [
      dirname
      for dirname in dirnames
      if not ignore_rules.should_ignore(current_path / dirname)
    ]
    
    for filename in filenames:
      file_path = current_path / filename
      
      if ignore_rules.should_ignore(file_path):
        continue
      
      if (
        file_path.suffix.lower() not in ALLOWED_EXTENSIONS
        and file_path.name not in ALLOWED_FILENAMES
      ):
        continue
      
      if file_path.stat().st_size > MAX_FILE_SIZE:
        continue
      
      relative_path = file_path.relative_to(root)
      result.append(relative_path)
  
  return sorted(result)
