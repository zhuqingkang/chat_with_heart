"""write_markdown - 写 Markdown 文件

复用 write_file 的 save_text 核心；差异点：
path 没有 markdown 扩展名时自动补 .md，避免模型写出无扩展名文件。
"""

from function_call.base.write.write_file import save_text


def write_markdown(args):
    path, content = args["path"], args["content"]
    if not path.lower().endswith((".md", ".markdown")):
        path += ".md"
    ok, note = save_text(path, content)
    if not ok:
        return note
    result = f"已写入 {path}（{len(content)} 字符）"
    return f"{result}，{note}" if note else result
