# Codex 多账号登录与保活说明

这份文档记录如何用不同的 `CODEX_HOME` 保存多个 Codex 登录环境，并用 `tmux` 让某个账号环境在后台保持运行。

## 1. 新建一个独立 Codex Home 并登录

```bash
mkdir -p ~/.codex-account2
CODEX_HOME=$HOME/.codex-account2 codex login
```

说明：

这会新建一个叫 `codex-account2` 的 Codex Home 环境，并在这个环境里登录第二个账号。它不会覆盖默认 `~/.codex` 里的账号。

## 2. 用指定账号环境启动 Codex

```bash
CODEX_HOME=$HOME/.codex-shizaishiwo323 codex
```

说明：

用 `shizaishiwo323` 这个 Codex Home 环境启动 Codex。

```bash
CODEX_HOME=$HOME/.codex-account2 codex
```

说明：

用 `codex-account2` 这个 Codex Home 环境启动 Codex，也就是启动第二个账号。

## 3. 查看当前 Codex CLI 进程使用哪个账号环境

```bash
for pid in $(pgrep -f "/opt/homebrew/bin/codex|/vendor/.*/codex/codex"); do
  echo "===== PID $pid ====="
  ps eww -p "$pid" | tr ' ' '\n' | grep CODEX_HOME || echo "未显示 CODEX_HOME，可能是默认 ~/.codex"
  echo
done
```

说明：

这会查看当前正在运行的 Codex CLI 进程，并显示每个进程正在使用哪个 `CODEX_HOME`。

如果没有显示 `CODEX_HOME`，说明它可能使用默认的 `~/.codex`。

## 4. 安装并检查 tmux

```bash
brew install tmux
```

说明：

安装 `tmux`，用于把 Codex 挂到后台运行。

```bash
tmux -V
```

说明：

检查 `tmux` 是否安装成功，并显示版本号。

## 5. 创建 tmux 会话并启动指定账号

```bash
tmux new -s codex-123
```

说明：

创建一个名为 `codex-123` 的 tmux 会话。

进入 tmux 会话后运行：

```bash
export CODEX_HOME=$HOME/.codex-shizaishiwo123
codex
```

说明：

把当前 tmux 会话切换到 `shizaishiwo123` 这个 Codex 环境，并在这个环境下启动 Codex。

## 6. 常用 tmux 操作

后台挂起当前 tmux 会话：

```bash
Ctrl-b 然后按 d
```

重新进入会话：

```bash
tmux attach -t codex-123
```

查看所有会话：

```bash
tmux list-sessions
```

关闭指定会话：

```bash
tmux kill-session -t codex-123
```

## 7. 和本项目账号池的关系

本项目的网页控制台读取的是各个账号目录里的 `auth.json`，例如：

```text
/Users/wangbin/.codex/auth.json
/Users/wangbin/.codex-shizaishiwo323/auth.json
/Users/wangbin/.codex-shizaishiwo123/auth.json
/Users/wangbin/.codex-shizaishiwo0/auth.json
```

如果你用新的 `CODEX_HOME` 登录了新账号，只需要把新目录里的 `auth.json` 配到 `config.py` 的 `ACCOUNTS` 里，网页控制台就能查询它的额度，并支持一键切换。
## 8. Windows 操作系统适配指令

下面说明如何在 Windows 下使用不同的 `CODEX_HOME` 保存多个 Codex 登录环境，并启动指定账号。

Windows 下推荐使用 **PowerShell**。如果你是在 **WSL / Ubuntu** 里使用 Codex，则继续使用前面 macOS / Linux 的命令即可。

---

## 8.1 新建一个独立 Codex Home 并登录

### PowerShell 写法

```powershell
mkdir $HOME\.codex-account2
$env:CODEX_HOME="$HOME\.codex-account2"
codex login
```

说明：

这会在 Windows 用户目录下新建一个独立的 Codex Home，例如：

```text
C:\Users\你的用户名\.codex-account2
```

然后在这个独立环境里登录第二个账号，不会覆盖默认的：

```text
C:\Users\你的用户名\.codex
```

---

## 8.2 用指定账号环境启动 Codex

### 启动 `codex-shizaishiwo323` 账号环境

```powershell
$env:CODEX_HOME="$HOME\.codex-shizaishiwo323"
codex
```

### 启动 `codex-account2` 账号环境

```powershell
$env:CODEX_HOME="$HOME\.codex-account2"
codex
```

说明：

PowerShell 中通过 `$env:CODEX_HOME="路径"` 设置当前终端窗口的环境变量。

这个设置只对当前 PowerShell 窗口有效。关闭窗口后不会影响系统全局环境变量。

---

## 8.3 一行命令启动指定账号

如果不想分两步写，也可以用下面的一行命令。

```powershell
$env:CODEX_HOME="$HOME\.codex-account2"; codex
```

例如：

```powershell
$env:CODEX_HOME="$HOME\.codex-shizaishiwo323"; codex
```

说明：

这会临时指定 `CODEX_HOME`，然后立刻启动 Codex。

---

## 8.4 CMD 写法

如果你使用的是传统 CMD，可以这样写：

```cmd
set CODEX_HOME=%USERPROFILE%\.codex-account2
codex login
```

启动指定账号：

```cmd
set CODEX_HOME=%USERPROFILE%\.codex-account2
codex
```

一行写法：

```cmd
set CODEX_HOME=%USERPROFILE%\.codex-account2 && codex
```

---

## 8.5 查看当前 PowerShell 窗口使用的 Codex Home

```powershell
echo $env:CODEX_HOME
```

说明：

如果有输出路径，例如：

```text
C:\Users\wangbin\.codex-account2
```

说明当前窗口正在使用这个 Codex Home。

如果没有输出，说明当前窗口可能使用默认的：

```text
C:\Users\wangbin\.codex
```

---

## 8.6 查看当前 Codex 进程

```powershell
Get-Process codex -ErrorAction SilentlyContinue
```

说明：

这会查看当前是否有正在运行的 Codex 进程。

如果没有输出，说明当前没有正在运行的 Codex CLI 进程。

---

## 8.7 Windows 下“后台保活”的替代方案

Windows 没有原生 `tmux`。常见替代方案有三种：

1. 使用 Windows Terminal 多标签页
2. 使用 PowerShell 新窗口后台运行
3. 使用 WSL 安装并使用 tmux

---

## 8.8 使用 Windows Terminal 启动指定账号

如果你安装了 Windows Terminal，可以用 `wt` 命令新开一个窗口并启动指定 Codex 账号。

```powershell
wt powershell -NoExit -Command "$env:CODEX_HOME='$HOME\.codex-account2'; codex"
```

例如启动 `shizaishiwo323`：

```powershell
wt powershell -NoExit -Command "$env:CODEX_HOME='$HOME\.codex-shizaishiwo323'; codex"
```

说明：

`-NoExit` 表示 Codex 结束后窗口不会自动关闭，方便查看输出。

---

## 8.9 使用 Start-Process 新开 PowerShell 窗口

```powershell
Start-Process powershell -ArgumentList '-NoExit', '-Command', '$env:CODEX_HOME="$HOME\.codex-account2"; codex'
```

例如：

```powershell
Start-Process powershell -ArgumentList '-NoExit', '-Command', '$env:CODEX_HOME="$HOME\.codex-shizaishiwo323"; codex'
```

说明：

这会新开一个 PowerShell 窗口，并在指定的 `CODEX_HOME` 环境下启动 Codex。

---

## 8.10 Windows 下推荐的账号目录示例

Windows 下账号池目录可以类似这样设置：

```text
C:\Users\wangbin\.codex\auth.json
C:\Users\wangbin\.codex-shizaishiwo323\auth.json
C:\Users\wangbin\.codex-shizaishiwo123\auth.json
C:\Users\wangbin\.codex-shizaishiwo0\auth.json
C:\Users\wangbin\.codex-account2\auth.json
```

在 Python 项目的 `config.py` 里可以写成：

```python
ACCOUNTS = [
    {
        "name": "default",
        "auth_path": r"C:\Users\wangbin\.codex\auth.json",
    },
    {
        "name": "shizaishiwo323",
        "auth_path": r"C:\Users\wangbin\.codex-shizaishiwo323\auth.json",
    },
    {
        "name": "shizaishiwo123",
        "auth_path": r"C:\Users\wangbin\.codex-shizaishiwo123\auth.json",
    },
    {
        "name": "account2",
        "auth_path": r"C:\Users\wangbin\.codex-account2\auth.json",
    },
]
```

注意：

Windows 路径建议使用 Python 原始字符串，也就是前面加 `r`：

```python
r"C:\Users\wangbin\.codex-account2\auth.json"
```

这样可以避免反斜杠 `\` 被 Python 误识别为转义字符。

---

## 8.11 如果使用 WSL / Ubuntu

如果你是在 Windows 的 WSL 里面使用 Codex，例如 Ubuntu 终端，那么仍然使用 Linux 写法：

```bash
mkdir -p ~/.codex-account2
CODEX_HOME=$HOME/.codex-account2 codex login
```

启动指定账号：

```bash
CODEX_HOME=$HOME/.codex-account2 codex
```

安装 tmux：

```bash
sudo apt update
sudo apt install tmux
```

创建 tmux 会话：

```bash
tmux new -s codex-123
```

进入 tmux 后运行：

```bash
export CODEX_HOME=$HOME/.codex-shizaishiwo123
codex
```

后台挂起：

```bash
Ctrl-b 然后按 d
```

重新进入：

```bash
tmux attach -t codex-123
```

查看所有会话：

```bash
tmux list-sessions
```

关闭指定会话：

```bash
tmux kill-session -t codex-123
```

---

## 8.12 Windows 使用建议

如果你只是想临时切换不同 Codex 账号，推荐使用 PowerShell：

```powershell
$env:CODEX_HOME="$HOME\.codex-account2"; codex
```

如果你想长期挂着某个账号，推荐使用 WSL + tmux，稳定性更接近 macOS / Linux：

```bash
tmux new -s codex-account2
export CODEX_HOME=$HOME/.codex-account2
codex
```

如果你不想折腾 WSL，也可以使用 Windows Terminal 多开几个标签页，每个标签页设置不同的 `CODEX_HOME`。
