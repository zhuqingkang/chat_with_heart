"""bash - 执行 shell 命令（流式输出 + 30 秒超时）

超时机制（v0.5 修复的死代码 bug）：
旧版把 proc.wait(timeout=30) 排在 for line in proc.stdout 之后，
但 for 只有进程退出（管道 EOF）才会结束，所以超时分支永远执行不到。
新版结构：
- 子线程 reader：逐行读管道 + 实时打印（和旧版行为一致）
- 主线程：t.join(30) 负责计时——不管输出有没有结束，时间到了就动手
- 超时后按「进程树」杀：Windows 下 shell=True 的真实命令是
  cmd 的孙进程，只 kill 父进程是杀不掉的，要用 taskkill /T /F
"""

import os
import subprocess
import threading

TIMEOUT = 30  # 命令最长执行秒数

# 实时输出用的颜色码（与 nanocode 本体的终端风格一致）
DIM, RESET = "\033[2m", "\033[0m"


def _kill_tree(proc):
    """杀整个进程树（Windows 用 taskkill /T，其他系统 kill 父进程）"""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,  # taskkill 自己的输出不要打到终端
        )
    else:
        proc.kill()


def bash(args):
    proc = subprocess.Popen(
        args["cmd"],
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",  # 命令输出编码不可控，坏字节替换掉，不崩溃
    )

    lines = []

    def reader():
        # 在子线程里跑：读管道 + 实时打印
        # （print 有内部锁，跨线程调用是安全的）
        for line in proc.stdout:
            print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
            lines.append(line)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    t.join(TIMEOUT)  # 主线程在这里计时，最多等 TIMEOUT 秒

    if t.is_alive():
        # 读还没结束 = 命令还活着（挂起或跑超了）
        _kill_tree(proc)
        t.join(5)  # 进程死后管道关闭，reader 会自然退出，给它时间收尾
        lines.append(f"\n(timed out after {TIMEOUT}s, killed)")
    else:
        proc.wait()  # 正常结束：EOF 已到，wait 立即返回

    return "".join(lines).strip() or "(empty)"
