from pathlib import Path

from config.settings import MAX_CONTEXT_FILES
from tools.read_file import read_file


def build_context(project_path: str, file_paths: list[str | Path]) -> str:
  context_parts: list[str] = []

  selected_files = file_paths[:MAX_CONTEXT_FILES]

  for file_path in selected_files:
    file_path_text = str(file_path)

    try:
      content = read_file(project_path, file_path_text)
    except Exception as error:
      context_parts.append(
        f"FILE: {file_path_text}\n"
        f"ERROR: {error}\n"
      )
      continue

    context_parts.append(
      f"FILE: {file_path_text}\n"
      "```text\n"
      f"{content}\n"
      "```\n"
    )

  return "\n".join(context_parts)