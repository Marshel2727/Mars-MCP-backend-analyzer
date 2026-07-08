from tools.read_file import read_file


MAX_READ_LINES = 200


def read_lines(
  project_path: str,
  file_path: str,
  start_line: int,
  end_line: int,
  max_lines: int = MAX_READ_LINES,
) -> str:
  if start_line <= 0:
    raise ValueError("start_line harus lebih besar dari 0.")

  if end_line < start_line:
    raise ValueError("end_line harus lebih besar atau sama dengan start_line.")

  if max_lines <= 0:
    raise ValueError("max_lines harus lebih besar dari 0.")

  line_count = end_line - start_line + 1

  if line_count > max_lines:
    end_line = start_line + max_lines - 1

  content = read_file(project_path, file_path)
  lines = content.splitlines()
  total_lines = len(lines)

  if start_line > total_lines:
    return (
      f"# Requested line range {start_line}-{end_line} is outside file. "
      f"File has {total_lines} lines."
    )

  actual_end_line = min(end_line, total_lines)
  selected_lines = lines[start_line - 1:actual_end_line]
  width = len(str(actual_end_line))

  return "\n".join(
    f"{line_number:>{width}}: {line}"
    for line_number, line in enumerate(selected_lines, start=start_line)
  )
