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
