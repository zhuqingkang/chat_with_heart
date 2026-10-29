"""distill - 会话结束自动蒸馏：把本次对话变成记忆条目（自动化写入）

借鉴厂商做法：蒸馏放在对话结束时触发（mem0 生产版是后台消息队列异步做，
我们是同步简单版——一次 API 调用，失败不阻塞退出）。
流程：messages → DeepSeek 按 DISTILL_PROMPT 抽条目（JSON）→
复用 remember 的完整写入流程（含冲突消解）→ 写入当日文件。
"""

import json
import re

from function_call.base.memory.memory_tools import remember

DISTILL_PROMPT = (
    "你是 nanocode 的记忆蒸馏器。阅读对话，提取 1-3 条值得长期保留的记忆"
    "（决策、偏好、情绪拐点；寒暄和过程性操作不要记）。\n"
    "只输出 JSON 数组，不要任何其他文字，格式：\n"
    '[{"title": "短标题", "event": "发生了什么（一两句）", '
    '"mood_label": "平静", "valence": 0.2, "arousal": 0.3, '
    '"affinity_delta": 1, "persona_note": "用户当时的性格表现"}]\n'
    "valence 取值 -1 到 1，arousal 0 到 1，affinity_delta -10 到 10。"
)


def distill_messages(messages, call_api):
    """把会话 messages 蒸馏写入当日记忆。

    call_api 由调用方传入（nanocode 的 call_api(messages, system_prompt)），
    避免 memory 包反向依赖 agent 本体。返回给用户看的摘要，无可写内容返回 None。
    """
    if not messages:
        return None
    resp = call_api(messages, DISTILL_PROMPT)
    text = resp["choices"][0]["message"].get("content") or ""
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return None  # 模型没按格式给 JSON，静默放弃（蒸馏是尽力而为）
    try:
        entries = json.loads(match.group())
    except json.JSONDecodeError:
        return None

    decisions = {"ADD": 0, "UPDATE": 0, "NOOP": 0}
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("event"):
            continue
        result = remember({
            "title": str(entry.get("title", "")),
            "event": str(entry["event"]),
            "mood_label": str(entry.get("mood_label", "平静")),
            "valence": entry.get("valence", 0.0),
            "arousal": entry.get("arousal", 0.3),
            "affinity_delta": entry.get("affinity_delta", 0),
            "persona_note": str(entry.get("persona_note", "")),
        })
        for key in decisions:
            if result.startswith(key) or f"（{key}）" in result:
                decisions[key] += 1
                break

    total = sum(decisions.values())
    if total == 0:
        return None
    return (
        f"记忆蒸馏完成：{total} 条 "
        f"(ADD {decisions['ADD']} / UPDATE {decisions['UPDATE']} / "
        f"NOOP {decisions['NOOP']})"
    )


def safe_distill(messages, call_api):
    """容错包装：蒸馏失败绝不阻塞退出流程"""
    try:
        return distill_messages(messages, call_api)
    except Exception:
        return None
