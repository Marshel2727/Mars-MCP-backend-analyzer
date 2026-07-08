from pathlib import Path

import pytest

from core.project_scanner import scan_project
from tools.read_file import read_file
from tools.read_lines import read_lines
from tools.search_code import search_code


def test_read_file_blocks_path_traversal(tmp_path: Path):
  project = tmp_path / "project"
  project.mkdir()
  outside = tmp_path / "outside.py"
  outside.write_text("secret = True\n", encoding="utf-8")

  with pytest.raises(PermissionError):
    read_file(str(project), "../outside.py")


def test_read_file_blocks_env(tmp_path: Path):
  project = tmp_path / "project"
  project.mkdir()
  env_file = project / ".env"
  env_file.write_text("SECRET_KEY=unsafe\n", encoding="utf-8")

  with pytest.raises(PermissionError):
    read_file(str(project), ".env")


def test_scan_project_skips_ignored_dirs(tmp_path: Path):
  project = tmp_path / "project"
  project.mkdir()
  ignored_dir = project / "node_modules"
  ignored_dir.mkdir()
  (ignored_dir / "ignored.py").write_text("print('ignore')\n", encoding="utf-8")
  (project / "app.py").write_text("print('scan')\n", encoding="utf-8")

  files = [str(file_path).replace("\\", "/") for file_path in scan_project(str(project))]

  assert "app.py" in files
  assert "node_modules/ignored.py" not in files


def test_read_lines_limits_max_lines(tmp_path: Path):
  project = tmp_path / "project"
  project.mkdir()
  lines = [f"line {number}" for number in range(1, 11)]
  (project / "app.py").write_text("\n".join(lines), encoding="utf-8")

  result = read_lines(str(project), "app.py", 1, 10, max_lines=3)

  assert result.splitlines() == [
    "1: line 1",
    "2: line 2",
    "3: line 3",
  ]


def test_search_code_returns_line_number(tmp_path: Path):
  project = tmp_path / "project"
  project.mkdir()
  (project / "app.py").write_text(
    "first line\nneedle is here\nlast line\n",
    encoding="utf-8",
  )

  results = search_code(str(project), "needle")

  assert results == [
    {
      "file": "app.py",
      "line": 2,
      "text": "needle is here",
    }
  ]
