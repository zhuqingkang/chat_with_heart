"""read_html - 读取 HTML 文件并提取纯文本

模型直接读原始 HTML 会被大量标签噪声干扰（一个页面里可见文本往往不到 30%）。
本工具用标准库 html.parser 提取可见文本：
- 跳过 <script> / <style> 内的内容（对理解页面没有帮助）
- 块级标签（p / div / h1-h6 / br / tr ...）处换行，保留基本结构
- 列表项加 "- " 前缀，接近 markdown 的阅读习惯

零第三方依赖；读文件复用 read_file 的 load_text。
"""

from html.parser import HTMLParser

from function_call.base.read.read_file import load_text

MAX_CHARS = 20000  # 提取后文本上限（字符），防止长页面撑爆上下文

# 这些标签处换行，保住文档结构
BLOCK_TAGS = {
    "p", "div", "section", "article", "header", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "tr", "blockquote", "pre", "ul", "ol", "br", "hr",
}
SKIP_TAGS = ("script", "style")  # 里面的内容对模型没有价值


class TextExtractor(HTMLParser):
    """把 HTMLParser 的流式事件拼成纯文本"""

    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0  # >0 表示当前在 script/style 内部

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth == 0 and data.strip():
            # 文本节点内部的换行和缩进折叠成一个空格
            self.parts.append(" ".join(data.split()))

    def get_text(self):
        text = "".join(self.parts)
        # 压掉连续 3 个以上的换行
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text.strip()


def read_html(args):
    lines = load_text(args["path"])
    if isinstance(lines, str):
        return lines

    extractor = TextExtractor()
    extractor.feed("".join(lines))
    text = extractor.get_text()

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n(... 已截断，共 {len(text)} 字符)"

    return text or "(空文件或没有可见文本)"
