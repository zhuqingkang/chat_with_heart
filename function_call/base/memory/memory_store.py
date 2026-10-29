"""memory_store - 记忆存储层（纯文件操作，不依赖 LLM）

借鉴 mem0 的冲突消解思路：写入新记忆前，先找相似的旧条目，规则判断
ADD（并存）/ UPDATE（替换旧条目）/ NOOP（跳过）。
一期用「字符 bigram 的 Jaccard 相似度」做判断；二期可换成 LLM 判断
（mem0 原版是让 LLM 对比新事实和旧事实后给出决策，见 DESIGN.md §6）。

目录约定（与 memory/DESIGN.md 一致）：
memory/<year>/<N>month/<yyyy_mm_dd>.md
"""

import json
import os
import re
from datetime import datetime

MEMORY_DIR = "memory"          # 相对 nanocode 的运行目录（项目根）
BASELINE_AFFINITY = 50         # system.md 里定义的初始好感度

# 冲突消解阈值（bigram Jaccard 相似度）
NOOP_THRESHOLD = 0.90          # 几乎相同 → 跳过
UPDATE_THRESHOLD = 0.60        # 明显相似（同一件事的补充/修正）→ 替换旧条目

AFFINITY_RE = re.compile(r"好感度：[+-]?\d+ → (\d+)")


# ---------- 路径 ----------

def day_path(dt=None):
    """当日记忆文件：memory/<year>/<N>month/<yyyy_mm_dd>.md"""
    dt = dt or datetime.now()
    return os.path.join(
        MEMORY_DIR, str(dt.year), f"{dt.month}month",
        f"{dt.year}_{dt.month:02d}_{dt.day:02d}.md",
    )


def month_path(dt=None):
    dt = dt or datetime.now()
    return os.path.join(MEMORY_DIR, str(dt.year), f"{dt.month}month", "month.md")


# ---------- 条目读写 ----------

def _read_entries(path):
    """把 md 文件按 '## ' 标题切成条目块列表（已 strip）"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    blocks = re.split(r"\n(?=## )", text)
    return [b.strip() for b in blocks if b.strip().startswith("## ")]


def _latest_affinity_from_logs():
    """按日期倒序扫所有日志文件，取最近一条累计好感度；找不到返回 None。

    文件名 yyyy_mm_dd.md 的字典序 = 日期序，倒序即从新到旧。
    """
    candidates = []
    for root, _dirs, files in os.walk(MEMORY_DIR):
        for name in files:
            if re.fullmatch(r"\d{4}_\d{2}_\d{2}\.md", name):
                candidates.append(os.path.join(root, name))
    for path in sorted(candidates, reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                values = AFFINITY_RE.findall(f.read())
        except OSError:
            continue
        if values:
            return int(values[-1])
    return None


def last_affinity(path=None):
    """当前好感度，三级兜底：
    1. state.json（updated_at 非空即有效，跨天持久）
    2. 历史日志按日期倒序找最近值——修复「state.json 诞生瞬间归零」缺口
       （旧版只看当日文件，10-29 第一条写入时无视了 10-28 的 56）
    3. 基线 50
    """
    state = load_state()
    if state["updated_at"]:
        return int(state["affinity"])
    logged = _latest_affinity_from_logs()
    if logged is not None:
        return logged
    return BASELINE_AFFINITY


def format_entry(title, event, mood_label, valence, arousal,
                 affinity_delta, new_affinity, persona_note):
    """生成 DESIGN.md §3 格式的一条记忆"""
    now = datetime.now()
    sign = f"+{affinity_delta}" if affinity_delta >= 0 else str(affinity_delta)
    return (
        f"## {now:%H:%M} {title}\n"
        f"- 事件：{event}\n"
        f"- 心情：{mood_label}（valence {valence:+.1f}，arousal {arousal:.1f}）\n"
        f"- 性格表现：{persona_note}\n"
        f"- 好感度：{sign} → {new_affinity}\n"
    )


def append_entry(entry_text, path=None):
    """把一条记忆追加到当日文件（不存在则先建带标题头的文件）"""
    path = path or day_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    need_header = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if need_header:
            dt = datetime.now()
            f.write(
                f"# {dt:%Y-%m-%d} 对话记忆\n\n"
                f"> 由 nanocode 自动蒸馏写入。格式规范见 memory/DESIGN.md §3。\n"
            )
        f.write("\n" + entry_text.rstrip() + "\n")
    return path


def replace_entry(old_block, new_block, path=None):
    """UPDATE：把旧条目块原位替换为新条目。成功返回 True"""
    path = path or day_path()
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if old_block not in text:
        return False
    text = text.replace(old_block, new_block.strip())
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


# ---------- 冲突消解（借鉴 mem0 的 ADD/UPDATE/DELETE/NOOP，一期规则版）----------

def _bigrams(text):
    """中文没空格分词，用相邻双字做最小语义单元"""
    text = re.sub(r"\W", "", text)
    return {text[i:i + 2] for i in range(len(text) - 1)} if len(text) > 1 else {text}


def similarity(a, b):
    """两段文本的 bigram Jaccard 相似度 0~1"""
    set_a, set_b = _bigrams(a), _bigrams(b)
    union = set_a | set_b
    return len(set_a & set_b) / len(union) if union else 0.0


def decide_action(event, path=None):
    """对比当日已有条目的「事件」字段，返回 (决策, 最相似的旧块或 None)。

    - 相似度 >= 0.90：几乎在重复记录同一件事 → NOOP
    - 0.60 ~ 0.90：同一件事的新进展/修正 → UPDATE（原位替换旧条目）
    - < 0.60：新事件 → ADD
    """
    path = path or day_path()
    best_block, best_sim = None, 0.0
    for block in _read_entries(path):
        match = re.search(r"- 事件：(.+)", block)
        if match:
            sim = similarity(event, match.group(1))
            if sim > best_sim:
                best_block, best_sim = block, sim
    if best_block is None or best_sim < UPDATE_THRESHOLD:
        return "ADD", None
    if best_sim >= NOOP_THRESHOLD:
        return "NOOP", best_block
    return "UPDATE", best_block


# ---------- 当前情感状态（state.json：记忆的"现在时"）----------
#
# 日志条目是记忆的"过去时"，当前状态必须有独立承载物：
# - 好感度不再依赖"当日最后一条"推导（原实现跨天会静默归零）
# - mood/valence/arousal 有了当前值，"语气随情绪变化"才有数据源
# 对应 Letta 的 core memory block 思路：常驻、显式、agent 可写。

STATE_PATH = os.path.join(MEMORY_DIR, "state.json")
STATE_DEFAULT = {
    "affinity": BASELINE_AFFINITY,
    "valence": 0.0,
    "arousal": 0.3,
    "mood_label": "平静",
    "updated_at": "",
}


def load_state():
    """读当前情感状态；文件缺失或损坏时逐字段兜底，绝不抛异常"""
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    state = dict(STATE_DEFAULT)
    state.update({key: data[key] for key in state if key in data})
    return state


def save_state(state):
    """持久化当前情感状态（remember 写完顺手调用）"""
    merged = dict(STATE_DEFAULT)
    merged.update({key: state[key] for key in merged if key in state})
    merged["updated_at"] = datetime.now().isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged


# ---------- 启动注入（读路径的"会话启动"场景）----------

def build_memory_prompt(max_chars=1200):
    """拼装启动时要注入 system prompt 的记忆文本。

    L0 人格层全文 + L1 全史层摘要（超长截断）。
    文件缺失或读取失败都返回兜底文案，绝不阻塞启动。
    """
    parts = []
    try:
        persona_path = os.path.join(MEMORY_DIR, "system.md")
        if os.path.exists(persona_path):
            with open(persona_path, "r", encoding="utf-8") as f:
                persona = f.read().strip()
            if persona:
                parts.append("【人格设定（用户定义，必须遵守）】\n" + persona)

        years_path = os.path.join(MEMORY_DIR, "years.md")
        if os.path.exists(years_path):
            with open(years_path, "r", encoding="utf-8") as f:
                history = f.read().strip()
            if history:
                if len(history) > max_chars:
                    history = history[:max_chars] + "\n(... 已截断)"
                parts.append("【长期记忆摘要】\n" + history)
    except Exception:
        pass  # 记忆读不到不阻塞启动，最多没人格

    if not parts:
        return "（长期记忆尚未建立：memory/system.md 与 years.md 待填写）"
    return "\n\n".join(parts)


# ---------- 检索 ----------

def search_entries(keyword, limit=10):
    """扫 memory/ 全部记忆文件，返回包含关键词的条目 [(路径, 块)]。

    排除 DESIGN.md（设计文档）和 system.md（人格常驻注入，无需检索）。
    """
    results = []
    for root, _dirs, files in os.walk(MEMORY_DIR):
        for name in files:
            if not name.endswith(".md") or name in ("DESIGN.md", "system.md"):
                continue
            path = os.path.join(root, name)
            for block in _read_entries(path):
                if keyword in block:
                    results.append((path, block))
                    if len(results) >= limit:
                        return results
    return results


def recent_entries(limit=8):
    """最近的记忆条目（跨文件，按日期倒序），供 Web 侧边栏展示。

    返回 [{"date","time","title","affinity","text"}]
    """
    files = []
    for root, _dirs, names in os.walk(MEMORY_DIR):
        for name in names:
            if re.fullmatch(r"\d{4}_\d{2}_\d{2}\.md", name):
                files.append(os.path.join(root, name))

    entries = []
    for path in sorted(files, reverse=True):  # 文件名序 = 日期倒序
        date = os.path.basename(path)[:-3]  # 去掉 .md
        for block in _read_entries(path):
            head = block.splitlines()[0]  # "## 21:30 标题"
            title = head.lstrip("# ").strip()
            parts = title.split(" ", 1)
            time = parts[0] if len(parts) > 1 else ""
            name = parts[1] if len(parts) > 1 else title
            match = AFFINITY_RE.search(block)
            entries.append({
                "date": date,
                "time": time,
                "title": name,
                "affinity": int(match.group(1)) if match else None,
                "text": block,
            })
            if len(entries) >= limit:
                return entries
    return entries
