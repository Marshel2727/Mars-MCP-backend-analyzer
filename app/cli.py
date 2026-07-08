import argparse
import re
from collections import defaultdict

from core.agent_runner import run_read_only_agent
from core.context_builder import build_context
from core.intent_profiles import get_available_depths
from core.planner import build_task_plan
from core.project_brief import build_project_brief
from core.project_map import build_project_map
from core.project_scanner import scan_project
from core.relevance import find_relevant_files
from tools.list_folder import list_folder
from tools.outline_file import outline_file
from tools.read_file import read_file
from tools.read_lines import read_lines
from tools.search_code import search_code


CONTEXT_MODE_CHOICES = ("auto", "map", "full")
AGENT_DEPTH_CHOICES = get_available_depths()
PROMPT_MODE_CHOICES = ("auto", "ask", "review", "debug")


STOP_WORDS = {
  "ada",
  "agar",
  "akan",
  "apa",
  "atau",
  "audit",
  "bagaimana",
  "beri",
  "berikan",
  "bisa",
  "bug",
  "debug",
  "dan",
  "dari",
  "dengan",
  "error",
  "file",
  "fix",
  "gagal",
  "ini",
  "itu",
  "jelaskan",
  "kalo",
  "kalau",
  "kode",
  "mana",
  "pada",
  "perbaiki",
  "project",
  "review",
  "saja",
  "saya",
  "struktur",
  "the",
  "untuk",
  "yang",
}


def unique_files(files):
  seen = set()
  results = []

  for file in files:
    file_text = str(file)

    if file_text in seen:
      continue

    seen.add(file_text)
    results.append(file_text)

  return results


def extract_search_terms(question):
  words = re.findall(r"[a-zA-Z0-9_./-]+", question.lower())
  terms = []

  for word in words:
    if len(word) < 3:
      continue

    if word in STOP_WORDS:
      continue

    terms.append(word)

  return unique_files(terms)


def find_mentioned_files(question, project_files):
  question_text = question.lower().replace("\\", "/")
  results = []

  for file in project_files:
    file_text = str(file)
    normalized_file = file_text.lower().replace("\\", "/")

    if normalized_file in question_text:
      results.append(file_text)

  return results


def find_files_by_search(project_path, keywords, max_files):
  results = []

  for keyword in keywords:
    matches = search_code(project_path, keyword, max_results=max_files * 5)
    results.extend(match["file"] for match in matches)

    if len(unique_files(results)) >= max_files:
      break

  return unique_files(results)[:max_files]


def find_files_by_auto_score(project_path, question, project_files, max_files):
  terms = extract_search_terms(question)

  if not terms:
    return []

  scores = defaultdict(int)

  for file in project_files:
    file_text = str(file).lower().replace("\\", "/")

    for term in terms:
      if term in file_text:
        scores[str(file)] += 3

  for term in terms[:8]:
    matches = search_code(project_path, term, max_results=max_files * 5)

    for match in matches:
      scores[match["file"]] += 1

  ranked_files = sorted(
    scores,
    key=lambda file: (-scores[file], file),
  )

  return ranked_files[:max_files]


def select_context_files(args):
  if args.files:
    return unique_files(args.files)[:args.max_files]

  if args.search:
    searched_files = find_files_by_search(
      args.project_path,
      args.search,
      args.max_files,
    )

    if searched_files:
      return searched_files

  project_files = scan_project(args.project_path)
  mentioned_files = find_mentioned_files(args.question, project_files)

  if mentioned_files:
    return mentioned_files[:args.max_files]

  if not args.no_auto:
    auto_files = find_files_by_auto_score(
      args.project_path,
      args.question,
      project_files,
      args.max_files,
    )

    if auto_files:
      return auto_files

  return project_files[:args.max_files]


def ask_llm(project_path, question, files, mode="auto", context_mode="auto"):
  from llm.ollama_provider import OllamaProvider
  from llm.prompt_templates import build_project_question_prompt, normalize_prompt_mode

  prompt_mode = normalize_prompt_mode(mode, question)

  if context_mode == "map":
    context = build_project_map(project_path)
  elif context_mode == "full":
    context = build_context(project_path, files)
  elif prompt_mode == "ask":
    context = build_project_map(project_path)
  else:
    context = build_context(project_path, files)

  prompt = build_project_question_prompt(question, context, mode=prompt_mode)

  provider = OllamaProvider()

  for chunk in provider.generate_stream(prompt):
    print(chunk, end="", flush=True)

  print()


def explain_file(project_path, file_path):
  from llm.ollama_provider import OllamaProvider
  from llm.prompt_templates import build_file_explanation_prompt

  content = read_file(project_path, file_path)
  prompt = build_file_explanation_prompt(file_path, content)

  provider = OllamaProvider()

  for chunk in provider.generate_stream(prompt):
    print(chunk, end="", flush=True)

  print()


def get_prompt_mode(args):
  return getattr(args, "prompt_mode", getattr(args, "mode", "auto"))


def get_context_mode(args):
  context_mode = getattr(args, "context", "auto")

  if context_mode != "auto":
    return context_mode

  if getattr(args, "files", None) or getattr(args, "search", None):
    return "full"

  return "auto"


def print_chat_help():
  print("Commands:")
  print("  /help                 tampilkan bantuan")
  print("  /files <file...>      pakai file tertentu untuk pertanyaan berikutnya")
  print("  /auto                 kembali ke pemilihan context otomatis")
  print("  /scan                 tampilkan file project")
  print("  /search <keyword>     cari keyword di project")
  print("  /clear                hapus file manual")
  print("  mode prompt           diatur dari command awal: auto, ask, review, debug")
  print("  /exit                 keluar")


def chat_select_files(project_path, question, max_files, manual_files):
  if manual_files:
    return unique_files(manual_files)[:max_files]

  args = argparse.Namespace(
    project_path=project_path,
    question=question,
    max_files=max_files,
    files=None,
    search=None,
    no_auto=False,
  )

  return select_context_files(args)


def handle_chat(args):
  manual_files = []

  print("Mars Project Analyzer Chat")
  print(f"Project: {args.project_path}")
  print("Ketik /help untuk bantuan, /exit untuk keluar.")

  while True:
    try:
      user_input = input("\nmars> ").strip()
    except (EOFError, KeyboardInterrupt):
      print()
      break

    if not user_input:
      continue

    if user_input in {"/exit", "/quit"}:
      break

    if user_input == "/help":
      print_chat_help()
      continue

    if user_input == "/auto":
      manual_files = []
      print("Context: auto")
      continue

    if user_input == "/clear":
      manual_files = []
      print("Manual files cleared.")
      continue

    if user_input == "/scan":
      for file in scan_project(args.project_path):
        print(file)
      continue

    if user_input.startswith("/files "):
      manual_files = user_input.split()[1:]
      print("Manual files:")
      for file in manual_files:
        print(f"- {file}")
      continue

    if user_input.startswith("/search "):
      keyword = user_input.removeprefix("/search ").strip()
      results = search_code(args.project_path, keyword, args.max_results)

      for result in results:
        print(f"{result['file']}:{result['line']} {result['text']}")
      continue

    selected_files = chat_select_files(
      args.project_path,
      user_input,
      args.max_files,
      manual_files,
    )

    if args.show_files:
      print("Context files:")
      for file in selected_files:
        print(f"- {file}")
      print()

    context_mode = args.context

    if manual_files and context_mode == "auto":
      context_mode = "full"

    ask_llm(
      args.project_path,
      user_input,
      selected_files,
      mode=args.mode,
      context_mode=context_mode,
    )


def handle_ask(args):
  selected_files = select_context_files(args)
  ask_llm(
    args.project_path,
    args.question,
    selected_files,
    mode=get_prompt_mode(args),
    context_mode=get_context_mode(args),
  )


def handle_ask_file(args):
  ask_llm(
    args.project_path,
    args.question,
    [args.file_path],
    mode=get_prompt_mode(args),
    context_mode="full",
  )


def handle_ask_files(args):
  ask_llm(
    args.project_path,
    args.question,
    args.files,
    mode=get_prompt_mode(args),
    context_mode="full",
  )


def handle_explain_file(args):
  explain_file(args.project_path, args.file_path)


def handle_agent(args):
  from llm.ollama_provider import OllamaProvider

  provider = OllamaProvider()
  response = run_read_only_agent(
    args.project_path,
    args.question,
    provider,
    max_steps=args.max_steps,
    depth=args.depth,
    verbose=args.trace or not args.quiet,
  )

  print(response)


def handle_scan(args):
  files = scan_project(args.project_path)

  for file in files:
    print(file)


def handle_read(args):
  content = read_file(args.project_path, args.file_path)

  print(content)


def handle_outline(args):
  outline = outline_file(args.project_path, args.file_path)

  print(outline)


def handle_list(args):
  items = list_folder(args.project_path, args.folder_path)

  for item in items:
    print(f"{item['type']}\t{item['path']}")


def handle_search(args):
  results = search_code(args.project_path, args.keyword, args.max_results)

  for result in results:
    print(f"{result['file']}:{result['line']} {result['text']}")


def handle_context(args):
  context = build_context(args.project_path, args.files)

  print(context)


def handle_project_map(args):
  context = build_project_map(
    args.project_path,
    max_files=args.max_files,
    max_symbols_per_file=args.max_symbols,
  )

  print(context)


def handle_project_brief(args):
  import json

  brief = build_project_brief(
    args.project_path,
    max_files_per_layer=args.max_files_per_layer,
    max_symbols=args.max_symbols,
  )

  print(json.dumps(brief, indent=2, ensure_ascii=False))


def handle_relevant_files(args):
  import json

  files = find_relevant_files(
    args.project_path,
    args.question,
    max_files=args.max_files,
    max_symbols=args.max_symbols,
  )

  print(json.dumps(files, indent=2, ensure_ascii=False))


def handle_read_lines(args):
  content = read_lines(
    args.project_path,
    args.file_path,
    args.start_line,
    args.end_line,
    max_lines=args.max_lines,
  )

  print(content)


def handle_plan(args):
  import json

  plan = build_task_plan(
    args.project_path,
    args.question,
    depth=args.depth,
  )

  print(json.dumps(plan, indent=2, ensure_ascii=False))


def main():
  parser = argparse.ArgumentParser(
    prog="mars-project-analyzer",
    description="Local AI project analyzer tools",
  )

  subparsers = parser.add_subparsers(dest="command", required=True)

  scan_parser = subparsers.add_parser("scan")
  scan_parser.add_argument("project_path")
  scan_parser.set_defaults(func=handle_scan)

  read_parser = subparsers.add_parser("read")
  read_parser.add_argument("project_path")
  read_parser.add_argument("file_path")
  read_parser.set_defaults(func=handle_read)

  outline_parser = subparsers.add_parser("outline")
  outline_parser.add_argument("project_path")
  outline_parser.add_argument("file_path")
  outline_parser.set_defaults(func=handle_outline)

  list_parser = subparsers.add_parser("list")
  list_parser.add_argument("project_path")
  list_parser.add_argument("folder_path", nargs="?", default=".")
  list_parser.set_defaults(func=handle_list)

  search_parser = subparsers.add_parser("search")
  search_parser.add_argument("project_path")
  search_parser.add_argument("keyword")
  search_parser.add_argument("--max-results", type=int, default=50)
  search_parser.set_defaults(func=handle_search)

  context_parser = subparsers.add_parser("context")
  context_parser.add_argument("project_path")
  context_parser.add_argument("files", nargs="+")
  context_parser.set_defaults(func=handle_context)

  project_map_parser = subparsers.add_parser("project-map")
  project_map_parser.add_argument("project_path")
  project_map_parser.add_argument("--max-files", type=int, default=200)
  project_map_parser.add_argument("--max-symbols", type=int, default=12)
  project_map_parser.set_defaults(func=handle_project_map)

  project_brief_parser = subparsers.add_parser("project-brief")
  project_brief_parser.add_argument("project_path")
  project_brief_parser.add_argument("--max-files-per-layer", type=int, default=5)
  project_brief_parser.add_argument("--max-symbols", type=int, default=4)
  project_brief_parser.set_defaults(func=handle_project_brief)

  relevant_files_parser = subparsers.add_parser("relevant-files")
  relevant_files_parser.add_argument("project_path")
  relevant_files_parser.add_argument("question")
  relevant_files_parser.add_argument("--max-files", type=int, default=8)
  relevant_files_parser.add_argument("--max-symbols", type=int, default=6)
  relevant_files_parser.set_defaults(func=handle_relevant_files)

  read_lines_parser = subparsers.add_parser("read-lines")
  read_lines_parser.add_argument("project_path")
  read_lines_parser.add_argument("file_path")
  read_lines_parser.add_argument("start_line", type=int)
  read_lines_parser.add_argument("end_line", type=int)
  read_lines_parser.add_argument("--max-lines", type=int, default=200)
  read_lines_parser.set_defaults(func=handle_read_lines)

  plan_parser = subparsers.add_parser("plan")
  plan_parser.add_argument("project_path")
  plan_parser.add_argument("question")
  plan_parser.add_argument("--depth", choices=("quick", "normal", "deep"), default="normal")
  plan_parser.set_defaults(func=handle_plan)
  
  ask_parser = subparsers.add_parser("ask")
  ask_parser.add_argument("project_path")
  ask_parser.add_argument("question")
  ask_parser.add_argument("--max-files", type=int, default=10)
  ask_parser.add_argument("--files", nargs="+")
  ask_parser.add_argument("--search", nargs="+")
  ask_parser.add_argument("--no-auto", action="store_true")
  ask_parser.add_argument("--mode", choices=PROMPT_MODE_CHOICES, default="auto")
  ask_parser.add_argument("--context", choices=CONTEXT_MODE_CHOICES, default="auto")
  ask_parser.set_defaults(func=handle_ask)

  ask_file_parser = subparsers.add_parser("ask-file")
  ask_file_parser.add_argument("project_path")
  ask_file_parser.add_argument("file_path")
  ask_file_parser.add_argument("question")
  ask_file_parser.add_argument("--mode", choices=PROMPT_MODE_CHOICES, default="auto")
  ask_file_parser.set_defaults(func=handle_ask_file)

  ask_files_parser = subparsers.add_parser("ask-files")
  ask_files_parser.add_argument("project_path")
  ask_files_parser.add_argument("question")
  ask_files_parser.add_argument("files", nargs="+")
  ask_files_parser.add_argument("--mode", choices=PROMPT_MODE_CHOICES, default="auto")
  ask_files_parser.set_defaults(func=handle_ask_files)

  review_parser = subparsers.add_parser("review")
  review_parser.add_argument("project_path")
  review_parser.add_argument("question")
  review_parser.add_argument("--max-files", type=int, default=10)
  review_parser.add_argument("--files", nargs="+")
  review_parser.add_argument("--search", nargs="+")
  review_parser.add_argument("--no-auto", action="store_true")
  review_parser.set_defaults(func=handle_ask, prompt_mode="review")

  review_file_parser = subparsers.add_parser("review-file")
  review_file_parser.add_argument("project_path")
  review_file_parser.add_argument("file_path")
  review_file_parser.add_argument("question", nargs="?", default="Review kode file ini.")
  review_file_parser.set_defaults(func=handle_ask_file, prompt_mode="review")

  review_files_parser = subparsers.add_parser("review-files")
  review_files_parser.add_argument("project_path")
  review_files_parser.add_argument("question")
  review_files_parser.add_argument("files", nargs="+")
  review_files_parser.set_defaults(func=handle_ask_files, prompt_mode="review")

  debug_parser = subparsers.add_parser("debug")
  debug_parser.add_argument("project_path")
  debug_parser.add_argument("question")
  debug_parser.add_argument("--max-files", type=int, default=10)
  debug_parser.add_argument("--files", nargs="+")
  debug_parser.add_argument("--search", nargs="+")
  debug_parser.add_argument("--no-auto", action="store_true")
  debug_parser.set_defaults(func=handle_ask, prompt_mode="debug")

  debug_file_parser = subparsers.add_parser("debug-file")
  debug_file_parser.add_argument("project_path")
  debug_file_parser.add_argument("file_path")
  debug_file_parser.add_argument("question")
  debug_file_parser.set_defaults(func=handle_ask_file, prompt_mode="debug")

  debug_files_parser = subparsers.add_parser("debug-files")
  debug_files_parser.add_argument("project_path")
  debug_files_parser.add_argument("question")
  debug_files_parser.add_argument("files", nargs="+")
  debug_files_parser.set_defaults(func=handle_ask_files, prompt_mode="debug")

  explain_file_parser = subparsers.add_parser("explain-file")
  explain_file_parser.add_argument("project_path")
  explain_file_parser.add_argument("file_path")
  explain_file_parser.set_defaults(func=handle_explain_file)

  agent_parser = subparsers.add_parser("agent")
  agent_parser.add_argument("project_path")
  agent_parser.add_argument("question")
  agent_parser.add_argument("--depth", choices=AGENT_DEPTH_CHOICES, default="normal")
  agent_parser.add_argument("--max-steps", type=int)
  agent_parser.add_argument("--quiet", action="store_true")
  agent_parser.add_argument("--trace", action="store_true")
  agent_parser.set_defaults(func=handle_agent)

  chat_parser = subparsers.add_parser("chat")
  chat_parser.add_argument("project_path")
  chat_parser.add_argument("--max-files", type=int, default=8)
  chat_parser.add_argument("--max-results", type=int, default=20)
  chat_parser.add_argument("--show-files", action="store_true")
  chat_parser.add_argument("--mode", choices=PROMPT_MODE_CHOICES, default="auto")
  chat_parser.add_argument("--context", choices=CONTEXT_MODE_CHOICES, default="auto")
  chat_parser.set_defaults(func=handle_chat)

  args = parser.parse_args()
  args.func(args)

