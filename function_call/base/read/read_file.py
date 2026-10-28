"""read_file - 读取文本文件的工具

设计要点（给 agent 用的工具，和普通函数不一样）：
1. 错误信息写给模型看：返回 "error: ..." 字符串，而不是抛异常，
   这样模型能读到错误原因并自己决定下一步（换文件、改路径等）
2. 截断到 500 行：防止大文件把对话上下文撑爆
3. 输出带 4 位行号：模型之后引用 "第 N 行" 有着落
"""

MAX_LINES = 500  # 最多返回多少行


def load_text(path):
    """读取文本文件：utf-8 失败后回退 gbk（Windows 中文文件常见）。

    成功返回行列表（每行含换行符）；失败返回 "error: ..." 字符串。
    read_file / read_html / read_markdown 共用这一层，保证错误行为一致。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.readlines()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="gbk") as f:
                return f.readlines()
        except UnicodeDecodeError:
            return f"error: 不是可读的文本文件（二进制或未知编码）: {path}"
    except FileNotFoundError:
        return f"error: 文件不存在: {path}"
    except PermissionError:
        return f"error: 没有权限读取: {path}"
    except OSError as err:
        return f"error: {err}"


def read_file(args):
    lines = load_text(args["path"])
    if isinstance(lines, str):
        return lines  # 出错时 load_text 返回的就是字符串

    # 拼带行号的文本，行号右对齐 4 位，方便模型精确引用
    output = []
    for i, line in enumerate(lines[:MAX_LINES]):
        output.append(f"{i + 1:4d} {line.rstrip()}")

    # 超过 500 行要告诉模型被截断了，需要更多内容时它可以用 bash + sed 取片段
    if len(lines) > MAX_LINES:
        output.append(f"(... 共 {len(lines)} 行，只显示前 {MAX_LINES} 行)")

    return "\n".join(output) or "(空文件)"
