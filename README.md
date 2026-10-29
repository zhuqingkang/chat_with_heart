# nanocode - 极简编码智能体

> **本项目基于 [1rgs/nanocode](https://github.com/1rgs/nanocode) 迭代开发。**
> 上游是一个约 200 行的 Python 单文件、零第三方依赖的极简 Claude Code 替代方案
> （DeepSeek + function calling + 双层循环）；本仓库保留了它的核心架构
> （REPL 外层 + agent loop 内层 + TOOLS 注册表），并在此基础上做了改造：
> 工具外置到 `function_call/` 包、工具扩展到 10 个、修复 bash 超时 bug 等。

一个零第三方依赖的命令行 coding agent：DeepSeek + function calling + 双层循环。
代码不到 200 行（本体），适合作为学习 agent 原理的最小范本。

**当前版本：v0.8**（更新于 2026-10-29）

## 记忆系统（一期已实现，2026-10-29）

跨会话记忆 + 情感模拟：五层记忆金字塔
（人格 system.md / 全史 years.md / 年 year.md / 月 month.md / 日 yyyy_mm_dd.md），
每条记忆带情感元数据（valence / arousal / 好感度 / 性格备注）。

一期能力（v0.7）：
- **remember** 工具：写入当日记忆，自动冲突消解（借鉴 mem0：
  bigram Jaccard 相似度 → ADD / UPDATE / NOOP 三决策），
  好感度累计值自动接续上一条；
- **recall** 工具：按日期精读当日文件，或按关键词扫描全部记忆；
- **自动蒸馏**：`/q` 退出、`/c` 清空时自动把本次对话交给 DeepSeek
  抽成 1-3 条记忆（含情感标注）写入当日文件，失败静默不阻塞。

二期规划：Milvus 语义检索（先 sqlite+numpy 过渡）、月/年蒸馏自动化、
LLM 版冲突消解、mood_report 情感时序报告。
完整设计见 [memory/DESIGN.md](memory/DESIGN.md)。

## 运行方式

```bash
# 环境变量
export DEEPSEEK_API_KEY=sk-xxx   # 必填
export MODEL=deepseek-chat       # 可选，覆盖默认模型

python nanocode.py
```

会话内命令：`/q`、`exit` 或 `quit` 退出、`/c` 清空对话历史——
退出和清空都会先把本次对话自动蒸馏进记忆（v0.7）。

## Web 前端（v0.8）

```bash
python web_server.py      # 浏览器打开 http://localhost:8000
```

零第三方依赖（标准库 `http.server`）。前端视觉沿用 Edurag
integrated_qa_system 的深色玻璃拟态风格（左侧记忆面板 + 右侧对话区）。

| 路由 | 说明 |
|---|---|
| `GET /` | 聊天页面 |
| `GET /api/state` | 当前情感状态（好感度 / 心情 / 唤醒度） |
| `GET /api/memories` | 最近记忆条目（`?date=` 取当天全文） |
| `POST /api/chat` | 发消息 → agent 循环 → 返回 `{reply, meme, state}` |
| `POST /api/reset` | 清空当前会话上下文 |
| `GET /memes/*` | 表情包图片 |

**表情包库**：`memes/<情绪>/图片`，按 `memory/state.json` 的 `mood_label`
自动选图附在回复后（`function_call/base/system/meme.py` 的 `MOOD_MAP`
映射中文心情 → 目录）。现有 5 类占位 SVG（happy/calm/angry/sad/smug），
换成真图即可，见 `memes/README.md`。

**CLI 与 Web 共用同一套 agent 逻辑**：`nanocode.py` 抽出
`build_system_prompt()` 与 `run_turn()`，两个入口共享，避免行为分叉。

## 架构

```
nanocode.py                 # agent 本体：REPL 外层 + agent loop 内层
└── function_call/          # 工具包（按 <类别>/<工具名> 组织）
    └── base/
        ├── read/           # 读取类
        │   ├── read_file.py      # 共享层 load_text + 通用读取
        │   ├── read_html.py      # HTML → 纯文本
        │   ├── read_markdown.py  # 原文 + 标题大纲
        │   └── list_dir.py       # 列目录（探索项目结构）
        ├── write/          # 写入类
        │   ├── write_file.py     # 共享层 save_text + 通用写入
        │   ├── write_html.py     # 自动补 .html
        │   └── write_markdown.py # 自动补 .md
        └── git/            # 版本控制类
            └── git.py            # 快照 / 回滚 / status / log / diff
        └── exec/           # 执行类
            └── bash.py           # shell 命令（流式输出 + 30s 超时杀进程树）
        └── system/         # 系统信息类
        │   └── now.py            # 当前时间（含时区、星期、Unix 时间戳）
        └── memory/         # 记忆类（v0.7）
            ├── memory_store.py   # 存储层：条目读写、冲突消解（规则版）、检索
            ├── memory_tools.py   # remember / recall 工具接口
            └── distill.py        # 会话结束自动蒸馏（LLM 抽取 → 写入）
web_server.py             # Web 服务入口（标准库 http.server，v0.8）
web/
├── templates/index.html  # 聊天页面
└── static/
    ├── style.css         # 样式（沿用 Edurag integrated_qa_system 风格）
    └── app.js            # 前端逻辑（聊天 / 表情包 / 记忆面板）
memes/                    # 表情包库：memes/<情绪>/图片
```

### 核心机制：双层循环

- **外层 REPL**：`input()` 等用户输入，维护 `messages` 历史列表。
- **内层 agent loop**：调模型 → 若返回 `tool_calls` 则执行工具、结果以
  `role: "tool"` 追加回 `messages` → 再调模型，直到模型不再请求工具。

### 工具注册表

新工具只需写进 `TOOLS` 字典，`make_schema()` 自动生成 function calling
参数定义，agent loop 无需改动。参数类型加 `?` 后缀表示可选（如 `"string?"`）。

## 工具清单（12 个）

| 工具 | 参数 | 说明 |
|---|---|---|
| bash | cmd | 执行 shell 命令，流式打印输出；30s 超时后杀整个进程树（v0.5 修复） |
| read_file | path | 读文本文件，带 4 位行号，截断 500 行，utf-8→gbk 回退 |
| read_html | path | 提取可见文本（去标签/跳过 script/style），上限 20000 字符 |
| read_markdown | path | 原文直出（无行号），前置标题大纲，正文截断 500 行 |
| list_dir | path? | 列目录：目录带 / 后缀、文件带大小，不递归，默认 cwd，截断 200 项 |
| write_file | path, content | 写文本，自动建父目录，utf-8；覆盖已有文件前自动 git 快照 |
| write_html | path, content | 同 write_file，无扩展名时自动补 .html |
| write_markdown | path, content | 同 write_file，无扩展名时自动补 .md |
| git | action, commit? | snapshot（全量提交返回短 hash）/ restore（reset --hard，需 commit）/ status / log / diff；白名单 5 动作，首次自动 init |
| now | （无） | 当前本地时间 + 星期 + UTC 偏移 + Unix 时间戳 |
| remember | event, 其余可选 | 写入当日记忆（带情感元数据）；自动冲突消解 ADD/UPDATE/NOOP，好感度自动累计（v0.7） |
| recall | date?, keyword? | 按日期读当日记忆文件，或按关键词扫全部记忆条目（v0.7） |

设计约定：工具错误一律返回 `error: ...` 字符串（不抛异常），错误信息
写给模型看，模型可自行决定重试或换路径。

## 开发进度

### 已完成

- [x] v0.0 agent 本体：双层循环、TOOLS 注册表、schema 生成、终端 UI
- [x] v0.1 `read_file` 工具 + `function_call/` 包结构（2026-10-28）
- [x] v0.2 读写全家桶：read_html / read_markdown / write_file /
      write_html / write_markdown，读取共享层 `load_text`、
      写入共享层 `save_text`（2026-10-28）
- [x] v0.3 `list_dir`（探索项目结构）+ `git` 工具（手动快照 / 回滚 /
      status / log / diff，白名单封装，首次自动 init）（2026-10-28）
- [x] v0.4 write 前自动快照：save_text 覆盖已有文件前自动调
      `git snapshot`（新建文件跳过，避免垃圾提交；快照失败不阻断
      写入，但会在返回信息里警示模型）（2026-10-28）
- [x] v0.5 bash 工具外置到 `function_call/base/exec/`（本体只剩
      agent loop + UI）；修复超时死代码 bug：读输出移入子线程、
      主线程 `join(30)` 计时，超时 `taskkill /T /F` 杀进程树
      （Windows 下 shell=True 的真命令是孙进程）（2026-10-28）
- [x] v0.6 `now` 时间工具：当前本地时间 / 星期 / UTC 偏移 /
      Unix 时间戳，无参数（首例空参数工具）（2026-10-28）
- [x] v0.7 记忆系统一期：`memory/DESIGN.md` 完整方案 + 五层记忆金字塔
      落地；`remember`（写入 + 借鉴 mem0 的规则版冲突消解）、
      `recall`（日期/关键词检索）两工具；`/q`、`/c` 时自动蒸馏
      本次对话写入记忆（LLM 抽条目 + 情感标注 + 冲突消解）；
      system prompt 告知模型自身具备记忆能力（2026-10-29）
- [x] v0.8 Web 前端 + 表情包库：`web_server.py`（标准库 http.server
      零依赖）提供聊天 / 记忆 / 表情包路由；前端沿用 Edurag
      integrated_qa_system 的深色玻璃拟态风格；`memes/` 5 类情绪
      表情包目录 + `meme.py` 按心情选图；`nanocode.py` 抽出
      `build_system_prompt()` / `run_turn()`，CLI 与 Web 共用一套
      agent 逻辑（2026-10-29）

### 计划中

- [ ] 记忆系统二期：Milvus/sqlite 向量检索、月/年蒸馏自动化、
      LLM 版冲突消解、mood_report 情感时序
- [ ] 会话启动记忆注入：**部分完成**——`system.md` 全文 + `years.md`
      摘要已注入 system prompt；当月 `month.md` 情绪趋势尚未接入
- [ ] 上下文管理：messages 无限增长，长会话会超模型窗口
- [ ] 评估闭环：改完代码自动跑测试回喂结果（自我迭代的关键一环）

## 状态检查（2026-10-29）

对工作目录做了一次完整核对，结果如下。

### 核对结果

| 检查项 | 结果 |
|---|---|
| 工具注册数 | 12 个，与本文档工具表逐项一致（参数名/可选性均核对过） |
| 代码规模 | Python 1474 行（本体 + web_server + 14 个工具模块）；前端约 1360 行（style.css 954 为主） |
| 目录结构 | `function_call/base/` 下 6 类：read 4 / write 3 / git 1 / exec 1 / system 2 / memory 3 |
| 记忆文件 | 8 个齐备：DESIGN / system / years / 2026-year / 10month / 2 天日志 / state.json |
| Web 前端 | 后端 7 条路由 + 前端三件套齐全；静态资源路径与后端路由逐条对齐 ✓ |
| git 跟踪 | `memory/` 已解除跟踪（隐私）；`.gitignore` 已锚定 `/memory/`、补 `.idea/` |
| 未提交 | 已改：`README.md`、`memory_store.py`、`nanocode.py`；未跟踪：`meme.py`、`memes/`、`web/`、`web_server.py` |

### 此前未记录的工程修复（v0.7 之后）

1. **`.gitignore` 误伤代码包**——规则写成 `memory`（无斜杠）会匹配任意层级
   同名目录，把 `function_call/base/memory/` 整个代码包排除在版本控制外，
   别人 clone 会直接 ImportError。已改为 `/memory/` 锚定仓库根。
2. **好感度隔天归零**——`last_affinity()` 兜底只看当日文件，导致
   state.json 诞生的那一瞬间仍归零一次（10-28 的 56 → 10-29 的 51）。
   已改为三级兜底：state.json → 历史日志按日期倒序 → 基线 50。
3. **`memory/` 曾被 git 跟踪**——对话摘要含隐私内容，已
   `git rm -r --cached memory/` 解除索引跟踪，磁盘文件保留。
4. **bash 参数诊断**——裸 `KeyError('cmd')` 对模型没有诊断价值，改为返回
   实际收到的键名，便于定位模型是否幻觉了参数名。
5. **CLI/Web 逻辑重复**——抽出 `build_system_prompt()` 与 `run_turn()`
   后，`main()` 里残留的旧 prompt 拼装与第二份 agent loop 已收口，
   避免两个入口行为分叉。

### 下一步优先级

| 优先级 | 事项 |
|---|---|
| P0 | 提交当前工作区改动（v0.7 尾 + v0.8 全部内容尚未入库） |
| P1 | 启动注入补 `month.md` 当月情绪趋势；上下文裁剪（messages 无限增长） |
| P1 | 记忆系统二期：向量检索 / LLM 版冲突消解 / mood_report / 月年蒸馏自动化 |
| P2 | 蒸馏兜底：目前只在 `/q`、`/c` 触发，进程崩溃会丢一轮（建议 `atexit` + 每 N 轮） |
| P2 | 评估闭环：改完代码自动跑测试回喂结果（自我迭代的关键一环） |

## 已知问题

1. **MODEL 默认值 `deepseek-flash` 与官方命名不符**：官方模型名为
   `deepseek-chat` / `deepseek-reasoner`，默认值大概率 401/400。
2. **API_KEY 兜底写法冗余**：`os.environ.get` 与 `os.getenv` 等价，
   key 缺失时会发出 `Authorization: Bearer None`。
3. **写工具覆盖已有文件**：覆盖前已自动 git 快照兜底；残留风险是
   快照失败时（如 git 未安装）仍会覆盖，返回信息会提示模型。
4. **bash 报 `error: 'cmd'` 尚未定位**：静态核查代码自洽（schema 声明的
   参数名与函数读取的一致），该 KeyError 只可能来自模型运行时返回了
   错误的参数名；已加入键名诊断输出，待实测复现确认。
