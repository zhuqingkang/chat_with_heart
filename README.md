# nanocode - 极简编码智能体

一个零第三方依赖的命令行 coding agent：DeepSeek + function calling + 双层循环。
代码不到 200 行（本体），适合作为学习 agent 原理的最小范本。

**当前版本：v0.6**（更新于 2026-10-28）

## 运行方式

```bash
# 环境变量
export DEEPSEEK_API_KEY=sk-xxx   # 必填
export MODEL=deepseek-chat       # 可选，覆盖默认模型

python nanocode.py
```

会话内命令：`/q` 或 `exit` 退出，`/c` 清空对话历史。

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
            └── now.py            # 当前时间（含时区、星期、Unix 时间戳）
```

### 核心机制：双层循环

- **外层 REPL**：`input()` 等用户输入，维护 `messages` 历史列表。
- **内层 agent loop**：调模型 → 若返回 `tool_calls` 则执行工具、结果以
  `role: "tool"` 追加回 `messages` → 再调模型，直到模型不再请求工具。

### 工具注册表

新工具只需写进 `TOOLS` 字典，`make_schema()` 自动生成 function calling
参数定义，agent loop 无需改动。参数类型加 `?` 后缀表示可选（如 `"string?"`）。

## 工具清单（10 个）

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

### 计划中

- [ ] 上下文管理：messages 无限增长，长会话会超模型窗口
- [ ] 评估闭环：改完代码自动跑测试回喂结果（自我迭代的关键一环）

## 已知问题

1. **MODEL 默认值 `deepseek-flash` 与官方命名不符**：官方模型名为
   `deepseek-chat` / `deepseek-reasoner`，默认值大概率 401/400。
2. **API_KEY 兜底写法冗余**：`os.environ.get` 与 `os.getenv` 等价，
   key 缺失时会发出 `Authorization: Bearer None`。
3. **写工具覆盖已有文件**：覆盖前已自动 git 快照兜底；残留风险是
   快照失败时（如 git 未安装）仍会覆盖，返回信息会提示模型。
