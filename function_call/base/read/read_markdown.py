"""read_markdown - 读取 Markdown 文件

markdown 本身就是模型友好的纯文本格式，所以不做格式转换、
也不加行号（行号会污染代码块里的代码内容），直接给原文。

相对 read_file 的差异化价值：开头附一份「标题大纲」，
模型面对长文档时先看结构，再决定要不要细读某一段。
大纲提取会跳过 ``` 代码块（代码块里的 # 是注释，不是标题）。
"""

import re

from function_call.base.read.read_file import load_text

MAX_LINES = 500  # 正文最多返回行数，与 read_file 保持一致

HEADING = re.compile(r"^#{1,6}\s")  # 行首 1-6 个 # 加空格才算标题


def extract_outline(lines):
    """提取标题行作为大纲；用 ``` 围栏开关排除代码块内的 # 注释行"""
    outline = []
    in_code = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_code = not in_code  # 进出代码块
        elif not in_code and HEADING.match(line):
            outline.append(line.rstrip())
    return outline


def read_markdown(args):
    lines = load_text(args["path"])
    if isinstance(lines, str):
        return lines

    outline = extract_outline(lines)
    body = "".join(lines[:MAX_LINES]).rstrip()

    parts = []
    if outline:
        parts.append("【大纲】\n" + "\n".join(outline))
        parts.append("【正文】\n" + (body or "(正文为空)"))
    else:
        parts.append(body or "(空文件)")
    if len(lines) > MAX_LINES:
        parts.append(f"(... 共 {len(lines)} 行，正文只显示前 {MAX_LINES} 行)")

    return "\n\n".join(parts)
