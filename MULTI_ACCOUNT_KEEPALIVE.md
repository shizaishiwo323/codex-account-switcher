# Codex 多账号登录与保活说明

这份文档记录如何用不同的 `CODEX_HOME` 保存多个 Codex 登录环境，并用 `tmux` 让某个账号环境在后台保持运行。

## 1. 新建一个独立 Codex Home 并登录

```bash
mkdir -p ~/.codex-shizaishiwo1223
CODEX_HOME=$HOME/.codex-shizaishiwo1223 codex login
```

## 5. 创建 tmux 会话并启动指定账号

```bash
tmux new -s codex-shizaishiwo1223
```

说明：

创建一个名为 `codex-shizaishiwo1223` 的 tmux 会话。

进入 tmux 会话后运行：

```bash

export CODEX_HOME=$HOME/.codex-shizaishiwo1223
codex
```
重新进入会话：

```bash
tmux attach -t codex-shizaishiwo1223
```

说明：

这会新建一个叫 `codex-shizaishiwo1223` 的 Codex Home 环境，并在这个环境里登录第二个账号。它不会覆盖默认 `~/.codex` 里的账号。

## 2. 用指定账号环境启动 Codex

```bash
CODEX_HOME=$HOME/.codex-shizaishiwo1223 codex
```

说明：

用 `shizaishiwo323` 这个 Codex Home 环境启动 Codex。

```bash
CODEX_HOME=$HOME/.codex-shizaishiwo1223 codex
```

说明：

用 `codex-shizaishiwo1223` 这个 Codex Home 环境启动 Codex，也就是启动第二个账号。

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
tmux new -s codex-shizaishiwo1223
```

说明：

创建一个名为 `codex-shizaishiwo1223` 的 tmux 会话。

进入 tmux 会话后运行：

```bash

export CODEX_HOME=$HOME/.codex-shizaishiwo1223
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
tmux attach -t codex-shizaishiwo1223
```

重新进入 `shizaishiwo323` 账号对应的后台会话：

```bash
tmux attach -t codex-shizaishiwo1223
```

查看所有会话：

```bash
tmux list-sessions
```

关闭指定会话：

```bash
tmux kill-session -t codex-shizaishiwo1223
```

## 7. 和本项目账号池的关系

本项目的网页控制台读取的是各个账号目录里的 `auth.json`，例如：

```text
/Users/wangbin/.codex/auth.json
/Users/wangbin/.codex-shizaishiwo1223/auth.json
/Users/wangbin/.codex-shizaishiwo1223/auth.json
/Users/wangbin/.codex-shizaishiwo0/auth.json
```

如果你用新的 `CODEX_HOME` 登录了新账号，只要目录名形如 `.codex-账号id` 且里面存在 `auth.json`，网页控制台和保活脚本都会自动识别它。比如 `/Users/wangbin/.codex-shizaishiwo1223/auth.json` 会生成账号 id `zshi0509`，网页默认显示为 `仓库池 zshi0509`，tmux 会话名为 `codex-shizaishiwo1223`。

网页端可以直接控制每个仓库池账号的后台保活模式：

- `自动`：当前不会因为 `1周` 额度用完自动暂停，开机脚本会启动所有未手动停止的 `.codex-*` 账号。
- `启动`：手动强制启动后台保活。
- `停止`：手动停止后台保活，并阻止 launchd 自动拉起。
