# Codex 多账号后台保活脚本

本项目提供一个快捷脚本，用来自动扫描 `/Users/wangbin/.codex-*` 账号环境，并按网页端的保活策略检测这些账号是否应该在后台 tmux 会话里运行；如果应该运行但没有运行，就自动启动：

```text
/Users/wangbin/.codex-shizaishiwo0
/Users/wangbin/.codex-shizaishiwo123
/Users/wangbin/.codex-shizaishiwo323
/Users/wangbin/.codex-zshi0509
```

## 脚本位置

```bash
scripts/ensure_codex_keepalive.sh
```

这个脚本会按目录名创建对应的 tmux 会话：

```text
codex-shizaishiwo0
codex-shizaishiwo123
codex-shizaishiwo323
codex-zshi0509
```

每个会话里都会用对应的 `CODEX_HOME` 启动 `codex`，并固定工作目录为 `/Users/wangbin`：

```bash
export CODEX_HOME=/Users/wangbin/.codex-shizaishiwo1223
codex --cd /Users/wangbin
```

脚本启动前会自动在每个仓库池账号的 `config.toml` 里写入：

```toml
[projects."/Users/wangbin"]
trust_level = "trusted"
```

这样新账号第一次后台启动时也不会卡在工作目录授权确认。

## 保活策略

网页端每个仓库池账号都有三个模式：

- `自动`：默认模式。当前不会因为 `1周` 额度为 0 自动暂停，开机脚本会启动所有未手动停止的 `.codex-*` 账号。
- `启动`：手动强制保活，即使周额度为 0 也会启动。
- `停止`：手动停止保活，launchd 下一轮检查也不会重新拉起。

`keepalive_state.json` 是本地运行状态文件，不提交到仓库。

脚本还会在每天本地时间 00 点这一小时内，对每个正在运行且策略允许的 `.codex-*` 仓库池 tmux 会话发送一次：

```text
你好
```

发送状态记录在 `keepalive_ping_state.json`，同一天重复运行脚本不会重复发送。默认账号 `/Users/wangbin/.codex` 不会被扫描，也不会被发送保活消息。

如果某个仓库池账号的 `auth.json` 缺失、JSON 损坏，或明显缺少 Codex token/API key 字段，脚本会跳过这个账号并写日志，避免反复拉起马上失败的 tmux 会话。

## 手动运行一次

```bash
/Users/wangbin/Documents/Codex/codex-account-switcher/scripts/ensure_codex_keepalive.sh
```

## 查看是否已挂起

```bash
tmux list-sessions
```

或者查看脚本日志：

```bash
tail -n 80 /Users/wangbin/Documents/Codex/codex-account-switcher/logs/codex-keepalive.log
```

## 开机自动运行

LaunchAgent 配置文件在：

```bash
launchd/com.shizaishiwo.codex-keepalive.plist
```

安装到 macOS 当前用户：

```bash
mkdir -p ~/Library/LaunchAgents
cp /Users/wangbin/Documents/Codex/codex-account-switcher/launchd/com.shizaishiwo.codex-keepalive.plist ~/Library/LaunchAgents/com.shizaishiwo.codex-keepalive.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.shizaishiwo.codex-keepalive.plist
launchctl kickstart -k gui/$(id -u)/com.shizaishiwo.codex-keepalive
```

这个 LaunchAgent 会：

- 开机登录后自动运行一次
- 每 300 秒检查一次
- 如果某个账号对应的 tmux 会话不存在，并且策略允许保活，就自动启动

## 停止自动运行

```bash
launchctl bootout gui/$(id -u)/com.shizaishiwo.codex-keepalive
```

如果只想停止某个后台 Codex 会话：

```bash
tmux kill-session -t codex-shizaishiwo123
```

如果网页端把这个账号设置为 `自动` 或 `启动`，LaunchAgent 下一次检查时会自动补拉起这个会话；如果设置为 `停止`，则不会补拉起。

## 本地 Web 服务开机自启

账号额度控制台本身也有一个独立的 LaunchAgent：

```bash
launchd/com.shizaishiwo.codex-account-switcher.plist
```

它会在用户登录后启动本地服务，并用 `KeepAlive` 在服务退出后自动拉起：

```text
http://127.0.0.1:8765
```

安装或更新到 macOS 当前用户：

```bash
mkdir -p ~/Library/LaunchAgents
mkdir -p /Users/wangbin/Documents/Codex/codex-account-switcher/logs
cp /Users/wangbin/Documents/Codex/codex-account-switcher/launchd/com.shizaishiwo.codex-account-switcher.plist ~/Library/LaunchAgents/com.shizaishiwo.codex-account-switcher.plist
launchctl bootout gui/$(id -u)/com.shizaishiwo.codex-account-switcher 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.shizaishiwo.codex-account-switcher.plist
launchctl kickstart -k gui/$(id -u)/com.shizaishiwo.codex-account-switcher
```

停止自动运行：

```bash
launchctl bootout gui/$(id -u)/com.shizaishiwo.codex-account-switcher
```

服务启动脚本：

```bash
scripts/run_codex_account_switcher_app.sh
```

日志：

```text
logs/account-switcher.out.log
logs/account-switcher.err.log
```
