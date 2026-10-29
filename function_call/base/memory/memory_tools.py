"""memory_tools - 记忆工具的 args 接口层：remember / recall"""

import os
import re

from function_call.base.memory import memory_store as store


def _num(args, key, default, lo, hi):
    """取数值参数并夹在合法区间（模型可能给出离谱值或字符串）"""
    try:
        value = float(args.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(hi, value))


def remember(args):
    """写一条带情感标注的记忆，自动冲突消解。

    args: event（必填）；title / mood_label / valence / arousal /
          affinity_delta / persona_note 可选。
    好感度累计值自动计算：读当日最后一条 + 本条 delta。
    """
    event = str(args.get("event", "")).strip()
    if not event:
        return "error: event 不能为空"

    decision, old_block = store.decide_action(event)
    if decision == "NOOP":
        first_line = old_block.splitlines()[0]
        return f"已存在几乎相同的记忆，跳过（NOOP）：{first_line}"

    title = str(args.get("title", "")).strip() or event[:12]
    mood = str(args.get("mood_label", "平静")).strip() or "平静"
    valence = _num(args, "valence", 0.0, -1.0, 1.0)
    arousal = _num(args, "arousal", 0.3, 0.0, 1.0)
    delta = int(_num(args, "affinity_delta", 0, -10, 10))
    persona = str(args.get("persona_note", "")).strip() or "（未记录）"

    old_affinity = store.last_affinity()
    new_affinity = max(0, min(100, old_affinity + delta))
    entry = store.format_entry(title, event, mood, valence, arousal,
                               delta, new_affinity, persona)

    # 顺手更新"当前情感状态"（记忆的现在时），供下次启动与情绪表达使用
    store.save_state({
        "affinity": new_affinity,
        "valence": valence,
        "arousal": arousal,
        "mood_label": mood,
    })

    if decision == "UPDATE":
        ok = store.replace_entry(old_block, entry)
        if ok:
            old_title = old_block.splitlines()[0]
            return f"已替换旧记忆（UPDATE）：{old_title} → 当前好感度 {new_affinity}"
        # 替换失败（文件被动过等）就退回追加，不丢记忆
        store.append_entry(entry)
        return f"UPDATE 失败已退回 ADD，当前好感度 {new_affinity}"

    path = store.append_entry(entry)
    return f"已写入记忆（ADD）→ {path}，当前好感度 {new_affinity}"


def recall(args):
    """检索记忆。args: date?（yyyy-mm-dd，读当日文件）/ keyword?（全文找条目）"""
    date = str(args.get("date", "")).strip()
    keyword = str(args.get("keyword", "")).strip()

    if date:
        norm = date.replace("-", "_")
        if not re.fullmatch(r"\d{4}_\d{2}_\d{2}", norm):
            return "error: date 格式应为 yyyy-mm-dd"
        path = os.path.join(store.MEMORY_DIR, norm[:4],
                            f"{int(norm[5:7])}month", f"{norm}.md")
        if not os.path.exists(path):
            return f"没有 {date} 的记忆文件"
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip() or "(空文件)"

    if keyword:
        results = store.search_entries(keyword)
        if not results:
            return f"没有找到包含「{keyword}」的记忆"
        parts = [f"找到 {len(results)} 条相关记忆："]
        for path, block in results:
            parts.append(f"\n--- {path} ---\n{block}")
        return "\n".join(parts)

    return "error: recall 需要 date 或 keyword 至少一个"
