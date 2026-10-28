"""list_dir - 列出目录内容

模型探索项目结构的主要入口（比 bash 跑 ls 的输出更结构化）：
- 目录名带 / 后缀，文件名带可读大小
- 按名字排序，最多 200 项
- 不递归：模型一层一层看，防止一次输出过大

path 可选，默认 "."（当前工作目录）——参数表里用 "string?" 标记可选，
make_schema 会自动把它从 required 里排除。
"""

import os

MAX_ENTRIES = 200  # 最多返回多少项


def _human_size(num):
    """把字节数转成可读大小（KB / MB）"""
    if num < 1024:
        return f"{num} B"
    if num < 1024 * 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num / 1024 / 1024:.1f} MB"


def list_dir(args):
    path = args.get("path", ".")

    try:
        names = sorted(os.listdir(path))
    except FileNotFoundError:
        return f"error: 目录不存在: {path}"
    except NotADirectoryError:
        return f"error: 不是目录: {path}"
    except PermissionError:
        return f"error: 没有权限: {path}"
    except OSError as err:
        return f"error: {err}"

    if not names:
        return "(空目录)"

    lines = []
    for name in names[:MAX_ENTRIES]:
        full = os.path.join(path, name)
        if os.path.isdir(full):
            lines.append(f"{name}/")
        else:
            try:
                size = _human_size(os.path.getsize(full))
            except OSError:
                size = "?"  # 拿不到大小（被占用等）不报错，标个问号
            lines.append(f"{name} ({size})")

    if len(names) > MAX_ENTRIES:
        lines.append(f"(... 共 {len(names)} 项，只显示前 {MAX_ENTRIES} 项)")

    return "\n".join(lines)
