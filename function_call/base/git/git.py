"""git - 版本控制工具：快照、回滚、探索

为什么不直接让模型用 bash 跑 git？三个封装价值：
1. 白名单限定 5 个动作，模型无法执行 push / filter-branch 等危险操作
2. snapshot 把 add + commit 封装成原子操作，消息自动生成，返回短 hash
3. 首次使用自动 git init，模型零配置

动作一览（action 参数）：
- snapshot：暂存全部改动并提交，返回短 hash（回滚的锚点）；
  同时被 write_file 的 save_text 在覆盖已有文件前自动调用（快照兜底）
- restore ：reset --hard 到指定 commit（会丢弃未快照的改动！）
- status  ：工作区改动摘要（带分支行）
- log     ：最近 10 条快照
- diff    ：工作区 vs 最近一次快照，截断 300 行
"""

import subprocess
from datetime import datetime

MAX_DIFF_LINES = 300  # diff 输出最多返回行数


def _git(*args):
    """跑一条 git 命令。返回 (是否成功, 合并后的输出)。"""
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output


def _ensure_repo():
    """当前目录不在 git 仓库里就自动 init 一个（只影响本目录，不碰全局配置）。

    返回 None 表示可以继续；返回字符串表示出错。
    """
    ok, _ = _git("rev-parse", "--is-inside-work-tree")
    if ok:
        return None
    ok, output = _git("init")
    if not ok:
        return f"error: git init 失败: {output}"
    return None


def _no_snapshot_yet(output):
    """git 报错文案里表示'还没有任何提交'的几种说法"""
    keywords = ("unknown revision", "ambiguous", "does not have any commits")
    return any(k in output for k in keywords)


def snapshot():
    """全量快照：add -A + commit，返回短 hash。

    公开给 save_text 调用（write 工具覆盖已有文件前的自动兜底）。
    """
    err = _ensure_repo()
    if err:
        return err
    _git("add", "-A")
    ok, output = _git("commit", "-m", f"nanocode snapshot {datetime.now():%Y-%m-%d %H:%M:%S}")
    if not ok:
        if "nothing to commit" in output:
            return "没有改动，无需快照（工作区与上次快照一致）"
        return f"error: commit 失败: {output}"
    # 拿短 hash 返回给模型，作为之后 restore 的锚点
    ok, short = _git("rev-parse", "--short", "HEAD")
    return f"已快照 {short}"


def _restore(commit):
    if not commit:
        return "error: restore 需要 commit 参数（从 snapshot 的返回值或 log 里拿短 hash）"
    ok, output = _git("reset", "--hard", commit)
    if not ok:
        return f"error: 回滚失败: {output}"
    return f"已回滚到 {commit}\n{output}"


def _status():
    err = _ensure_repo()
    if err:
        return err
    ok, output = _git("status", "--short", "-b")
    if not ok:
        return f"error: {output}"
    return output or "工作区干净（与上次快照一致）"


def _log():
    ok, output = _git("log", "--oneline", "-10")
    if not ok:
        return "还没有任何快照（先执行 action=snapshot）"
    return output


def _diff():
    ok, output = _git("diff", "HEAD")
    if not ok:
        if _no_snapshot_yet(output):
            return "还没有任何快照（先执行 action=snapshot）"
        return f"error: {output}"
    lines = output.split("\n")
    if len(lines) > MAX_DIFF_LINES:
        output = "\n".join(lines[:MAX_DIFF_LINES]) + f"\n(... 截断，共 {len(lines)} 行)"
    return output or "没有改动（工作区与上次快照一致）"


def git_tool(args):
    action = args.get("action", "")

    if action == "snapshot":
        return snapshot()
    if action == "restore":
        return _restore(args.get("commit", ""))
    if action == "status":
        return _status()
    if action == "log":
        return _log()
    if action == "diff":
        return _diff()
    return "error: 未知 action，可选 snapshot / restore / status / log / diff"
