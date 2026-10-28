"""now - 获取当前系统时间

给模型的三个用途：知道"现在几点"（回答涉及时间的问题）、
拿 Unix 时间戳做时间差计算、确认时区（避免时间换算出错）。

无参数——时间不需要输入。TOOLS 里参数表传空字典 {} 即可，
make_schema 会生成空的 properties / required。
"""

from datetime import datetime

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def now(args):
    # astimezone() 不带参数 = 补上本地时区信息（变成 aware datetime）
    local = datetime.now().astimezone()
    return (
        f"当前时间：{local:%Y-%m-%d %H:%M:%S}（{WEEKDAYS[local.weekday()]}）\n"
        f"时区：UTC{local:%z}\n"
        f"Unix 时间戳：{int(local.timestamp())}"
    )
