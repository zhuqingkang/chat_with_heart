#!/usr/bin/env python3
"""nanocode - minimal coding agent"""

import json
import os
import re
import urllib.request

# --- 本地工具包 ---
from function_call.base.read.read_file import read_file
from function_call.base.read.read_html import read_html
from function_call.base.read.read_markdown import read_markdown
from function_call.base.read.list_dir import list_dir
from function_call.base.write.write_file import write_file
from function_call.base.write.write_html import write_html
from function_call.base.write.write_markdown import write_markdown
from function_call.base.git.git import git_tool
from function_call.base.exec.bash import bash
from function_call.base.system.now import now

# 声明三个常量KEY，URL，MODEL -> LLM
API_KEY = os.environ.get("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY"))
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = os.environ.get("MODEL", "deepseek-flash")

# ANSI colors 命令行控制字符
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, RED = "\033[34m", "\033[36m", "\033[32m", "\033[31m"


# hash tools
TOOLS = {
    "bash": (
        "Run shell command, streams output, 30s timeout then kills "
        "the whole process tree",
        {"cmd": "string"},
        bash,
    ),
    "read_file": (
        "Read a text file (utf-8 or gbk), returns up to 500 numbered lines",
        {"path": "string"},
        read_file,
    ),
    "read_html": (
        "Read an HTML file, extract visible text (tags/script/style removed)",
        {"path": "string"},
        read_html,
    ),
    "read_markdown": (
        "Read a Markdown file as-is, with a heading outline prepended",
        {"path": "string"},
        read_markdown,
    ),
    "write_file": (
        "Write text to a file (utf-8, creates parent dirs, overwrites)",
        {"path": "string", "content": "string"},
        write_file,
    ),
    "write_html": (
        "Write content to an .html file (auto .html extension, overwrites)",
        {"path": "string", "content": "string"},
        write_html,
    ),
    "write_markdown": (
        "Write content to a .md file (auto .md extension, overwrites)",
        {"path": "string", "content": "string"},
        write_markdown,
    ),
    "list_dir": (
        "List directory entries (dirs get / suffix, files show size), "
        "non-recursive, default cwd",
        {"path": "string?"},
        list_dir,
    ),
    "git": (
        "Git version control. action=snapshot (commit all changes, returns "
        "short hash) / restore (reset --hard to that commit, DISCARDS "
        "uncommitted changes, needs 'commit') / status / log (last 10) / "
        "diff (worktree vs last snapshot)",
        {"action": "string", "commit": "string?"},
        git_tool,
    ),
    "now": (
        "Get current local date/time, weekday, UTC offset and unix timestamp",
        {},
        now,
    ),
}


def run_tool(name, args):
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


# 拼工具描述
def make_schema():
    """Build OpenAI-compatible tools list from TOOLS.

    Param types may end with '?' to mark optional fields, e.g. {"path": "string?"}.
    """
    schema = []
    for name, (description, params, _) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            optional = param_type.endswith("?")
            properties[param_name] = {"type": param_type.rstrip("?")}
            if not optional:
                required.append(param_name)
        schema.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return schema


def call_api(messages, system_prompt):
    body = {
        "model": MODEL,
        "max_tokens": 8192,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "tools": make_schema(),
        "tool_choice": "auto",
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": "nanocode/1.0",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def separator():
    width = min(os.get_terminal_size().columns, 80)
    return f"{DIM}{'─' * width}{RESET}"


def render_markdown(text):
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def preview_result(result):
    result_lines = result.split("\n")
    preview = result_lines[0][:60]
    if len(result_lines) > 1:
        preview += f" ... +{len(result_lines) - 1} lines"
    elif len(result_lines[0]) > 60:
        preview += "..."
    return preview


def main():
    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} (DeepSeek) | {os.getcwd()}{RESET}\n")
    messages = []
    system_prompt = f"Concise coding assistant. cwd: {os.getcwd()}"


    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                messages = []
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})

            # agent loop: call model until it stops requesting tools
            while True:
                msg = call_api(messages, system_prompt)["choices"][0]["message"]
                text = msg.get("content") or ""
                tool_calls = msg.get("tool_calls") or []

                if text:
                    print(f"\n{CYAN}⏺{RESET} {render_markdown(text)}")

                assistant = {"role": "assistant", "content": text or None}
                if tool_calls:
                    assistant["tool_calls"] = tool_calls
                messages.append(assistant)

                # handle tool calls
                if not tool_calls:
                    break

                for call in tool_calls:
                    name = call["function"]["name"]
                    args = json.loads(call["function"]["arguments"])
                    arg_preview = str(next(iter(args.values()), ""))[:50]
                    print(f"\n{GREEN}⏺ {name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})")

                    result = run_tool(name, args)
                    print(f"  {DIM}⎿  {preview_result(result)}{RESET}")

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": result,
                        }
                    )

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()
