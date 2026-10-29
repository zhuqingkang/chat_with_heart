"""meme - 表情包库：按当前心情选一张图（Web 前端展示用）

目录约定：memes/<情绪目录>/xxx.(png|jpg|jpeg|gif|svg|webp)
情绪目录由 MOOD_MAP 映射（state.json 里存的是中文心情标签）。
CLI 端不渲染图片，这个模块只服务 Web 前端。
"""

import os
import random

MEME_DIR = "memes"
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

# 中文心情标签 → 表情包目录
MOOD_MAP = {
    "开心": "happy", "愉快": "happy", "兴奋": "excited",
    "得意": "smug", "傲娇": "smug",
    "平静": "calm", "专注": "calm", "务实": "calm", "干脆": "calm",
    "生气": "angry", "烦躁": "angry", "不满": "angry",
    "委屈": "sad", "难过": "sad", "受挫": "sad",
}


def pick_meme(mood_label, memes_dir=MEME_DIR):
    """按心情标签选一张表情包，返回 URL 路径；没有对应表情时返回 None。

    匹配顺序：子串包含（如"干脆、收尾"命中"干脆"）→ 精确匹配 → 同名目录。
    """
    if not mood_label:
        return None

    folder = None
    for key, value in MOOD_MAP.items():
        if key in mood_label:
            folder = value
            break
    if folder is None and mood_label in MOOD_MAP:
        folder = MOOD_MAP[mood_label]
    if folder is None and os.path.isdir(os.path.join(memes_dir, mood_label)):
        folder = mood_label
    if folder is None:
        return None

    folder_path = os.path.join(memes_dir, folder)
    if not os.path.isdir(folder_path):
        return None
    names = [n for n in os.listdir(folder_path) if n.lower().endswith(IMAGE_EXT)]
    if not names:
        return None
    return f"/memes/{folder}/{random.choice(names)}"
