# 表情包库

按情绪分目录放图，Web 前端会根据 `memory/state.json` 里的 `mood_label`
自动挑一张附在回复后面。

## 目录

| 目录 | 触发心情（中文标签） |
|---|---|
| `happy/` | 开心、愉快、兴奋 |
| `calm/` | 平静、专注、务实、干脆 |
| `smug/` | 得意、傲娇 |
| `angry/` | 生气、烦躁、不满 |
| `sad/` | 委屈、难过、受挫 |

## 怎么加自己的图

1. 把图片丢进对应情绪目录（`memes/happy/01.png` 这样）；
2. 支持 `.png` `.jpg` `.jpeg` `.gif` `.svg` `.webp`；
3. 想要新的情绪分类：在 `function_call/base/system/meme.py` 的 `MOOD_MAP`
   里加一条映射，并在 `memes/` 下建同名目录。

目录里现在只有占位 SVG（手绘简笔画），可以直接替换成真表情包。
