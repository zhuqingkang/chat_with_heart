"""write_file - 写文本文件的工具（write_html / write_markdown 的共享核心）

设计要点：
1. 自动创建父目录：模型给的 path 常常是不存在的多级路径
2. 统一 utf-8 写入（跨平台一致，避免 Windows 默认 gbk 引发的乱码）
3. 直接覆盖已有文件，但覆盖前会先自动做一次 git 快照兜底
   （新建文件没有旧版本可丢，跳过快照，避免产生垃圾提交）
"""

import os

from function_call.base.git.git import snapshot


def save_text(path, content):
    """把 content 写入 path（utf-8）。

    返回 (是否成功, 附加信息)：
    - 失败：附加信息是 "error: ..."（写入未发生）
    - 成功：附加信息是快照说明——新建文件为空串；覆盖已有文件时
      为 "覆盖前已快照 <hash>"；快照失败时为警示信息
    快照尽力而为：失败不阻断写入，但会把风险告知模型。
    """
    # 只在覆盖已有文件前快照：新文件没有旧内容可丢
    note = ""
    if os.path.exists(path):
        snap = snapshot()
        if snap.startswith("已快照"):
            note = f"覆盖前{snap}"
        elif snap.startswith("没有改动"):
            note = "旧版本已在最近一次快照中，可随时 git restore 找回"
        else:
            note = f"注意：{snap}，旧版本无法找回"

    try:
        parent = os.path.dirname(path)
        if parent:  # path 是纯文件名时 dirname 是空串，不用建目录
            os.makedirs(parent, exist_ok=True)
        # newline=""：按原样写换行符，不做 Windows 平台转换
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    except OSError as err:
        return False, f"error: {err}"
    return True, note


def write_file(args):
    ok, note = save_text(args["path"], args["content"])
    if not ok:
        return note
    result = f"已写入 {args['path']}（{len(args['content'])} 字符）"
    return f"{result}，{note}" if note else result
