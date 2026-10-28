"""write_html - 写 HTML 文件

复用 write_file 的 save_text 核心；差异点：
path 没有网页扩展名时自动补 .html，避免模型写出无扩展名文件。
"""

from function_call.base.write.write_file import save_text


def write_html(args):
    path, content = args["path"], args["content"]
    if not path.lower().endswith((".html", ".htm")):
        path += ".html"
    ok, note = save_text(path, content)
    if not ok:
        return note
    result = f"已写入 {path}（{len(content)} 字符）"
    return f"{result}，{note}" if note else result
