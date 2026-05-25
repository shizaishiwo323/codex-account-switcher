# Codex 多账号后台保活脚本

本项目提供一个快捷脚本，用来检测以下 3 个账号环境是否已经在后台 tmux 会话里运行；如果没有运行，就自动启动：

```text
/Users/wangbin/.codex-shizaishiwo0
/Users/wangbin/.codex-shizaishiwo123
/Users/wangbin/.codex-shizaishiwo323
```

## 脚本位置

```bash
scripts/ensure_codex_keepalive.sh
```

这个脚本会创建以下 tmux 会话：

```text
codex-shizaishiwo0
codex-shizaishiwo123
codex-shizaishiwo323
```

每个会话里都会用对应的 `CODEX_HOME` 启动 `codex`。

## 手动运行一次

```bash
/Users/wangbin/Documents/Codex/任意任务/codex-account-switcher/scripts/ensure_codex_keepalive.sh
```

## 查看是否已挂起

```bash
tmux list-sessions
```

或者查看脚本日志：

```bash
tail -n 80 /Users/wangbin/Documents/Codex/任意任务/codex-account-switcher/logs/codex-keepalive.log
```

## 开机自动运行

LaunchAgent 配置文件在：

```bash
launchd/com.shizaishiwo.codex-keepalive.plist
```

安装到 macOS 当前用户：

```bash
mkdir -p ~/Library/LaunchAgents
cp /Users/wangbin/Documents/Codex/任意任务/codex-account-switcher/launchd/com.shizaishiwo.codex-keepalive.plist ~/Library/LaunchAgents/com.shizaishiwo.codex-keepalive.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.shizaishiwo.codex-keepalive.plist
launchctl kickstart -k gui/$(id -u)/com.shizaishiwo.codex-keepalive
```

这个 LaunchAgent 会：

- 开机登录后自动运行一次
- 每 300 秒检查一次
- 如果某个账号对应的 tmux 会话不存在，就自动启动

## 停止自动运行

```bash
launchctl bootout gui/$(id -u)/com.shizaishiwo.codex-keepalive
```

如果只想停止某个后台 Codex 会话：

```bash
tmux kill-session -t codex-shizaishiwo123
```

LaunchAgent 下一次检查时会自动补拉起这个会话。
