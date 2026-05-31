# Codex Account Switcher

本地网页端 Codex 账号额度控制台。它会读取多个 Codex `auth.json`，展示每个账号的 5 小时和 1 周剩余额度，并支持一键切换当前 Codex 桌面端使用的认证文件。

## 功能

- 查询默认账号和仓库池账号的 Codex 用量
- 显示账号邮箱、Plus/Plan、5 小时剩余额度、1 周剩余额度和重置时间
- 一键切换账号
- 切换账号前会检查当前默认认证属于哪个仓库池账号；如默认认证更新过，会先备份默认认证和原账号池认证，再把默认认证回写到原账号池
- 支持把下载到的 `auth.json` 上传覆盖到指定仓库池账号；覆盖前会先比对，相同则跳过，不同则备份目标文件和上传文件
- 网页端控制每个仓库池账号的后台保活：自动、启动、停止
- 保留按 1 周额度自动暂停保活的代码开关；当前默认关闭，开机会启动所有未手动停止的账号
- 切换时自动关闭 Codex 桌面端
- 切换前自动备份当前默认认证文件；如果发生默认认证回写账号池，也会同时备份回写前的两边文件
- 覆盖 `/Users/wangbin/.codex/auth.json`
- 切换后重新打开 Codex 桌面端

## 默认账号路径

```python
DEFAULT_AUTH_PATH = Path("/Users/wangbin/.codex/auth.json")
```

## 仓库池路径

网页会自动扫描 `/Users/wangbin` 下所有名字形如 `.codex-*` 且包含 `auth.json` 的目录，例如：

```python
Path("/Users/wangbin/.codex-shizaishiwo0/auth.json")
Path("/Users/wangbin/.codex-shizaishiwo123/auth.json")
Path("/Users/wangbin/.codex-shizaishiwo323/auth.json")
Path("/Users/wangbin/.codex-zshi0509/auth.json")
```

## 新增仓库池账号

新账号不需要手动改 `config.py`。只要用新的 `CODEX_HOME` 登录，并保证目录名是 `.codex-账号id`、目录里存在登录好的 `auth.json`，刷新网页后就会自动出现：

```bash
mkdir -p ~/.codex-zshi0509
CODEX_HOME=$HOME/.codex-zshi0509 codex login
```

默认显示名会按目录名生成，例如 `.codex-zshi0509` 会显示为 `仓库池 zshi0509`。如果需要自定义显示名，可以在 `config.py` 的 `ACCOUNT_OVERRIDES` 里只覆盖 label，不需要维护完整账号列表。

## 多账号登录与保活

如果需要用多个 `CODEX_HOME` 登录不同账号，并用 `tmux` 挂后台保活，见：

[MULTI_ACCOUNT_KEEPALIVE.md](MULTI_ACCOUNT_KEEPALIVE.md)

如果需要开机自动检测并挂起所有 `.codex-*` 仓库池账号，见：

[CODEX_KEEPALIVE_LAUNCHD.md](CODEX_KEEPALIVE_LAUNCHD.md)

网页里每个仓库池账号都有后台保活控制：

- `自动`：默认模式。当前不会因为 `1周` 额度为 0 自动暂停，开机脚本会启动所有未手动停止的 `.codex-*` 账号。
- `启动`：手动强制保活，即使周额度为 0 也会启动对应 tmux 会话。
- `停止`：手动停止保活，并阻止 launchd 下一轮自动拉起。

保活状态保存在本地 `keepalive_state.json`，这个文件会被 `.gitignore` 忽略。

## 运行

```bash
python app.py
```

然后打开：

```text
http://127.0.0.1:8765
```

## 开机自启本地服务

本地 Web 服务可以通过当前用户的 macOS LaunchAgent 开机自启并崩溃后自动拉起：

```bash
mkdir -p ~/Library/LaunchAgents
mkdir -p /Users/wangbin/Documents/Codex/codex-account-switcher/logs
cp /Users/wangbin/Documents/Codex/codex-account-switcher/launchd/com.shizaishiwo.codex-account-switcher.plist ~/Library/LaunchAgents/com.shizaishiwo.codex-account-switcher.plist
launchctl bootout gui/$(id -u)/com.shizaishiwo.codex-account-switcher 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.shizaishiwo.codex-account-switcher.plist
launchctl kickstart -k gui/$(id -u)/com.shizaishiwo.codex-account-switcher
```

服务启动脚本是：

```bash
scripts/run_codex_account_switcher_app.sh
```

日志位置：

```text
logs/account-switcher.out.log
logs/account-switcher.err.log
```

## 公网入口

建议使用子域名：

```text
codex-quota.shizaishiwo.com
```

`config.py` 里的 `PUBLIC_MONITOR_HOSTS` 已把这个域名配置为公网入口。请求 Host 命中该域名时：

- 前端保留账号展示、额度查询、刷新、认证下载、认证上传和账号切换
- `/api/accounts` 会隐藏本机 `auth.json` 路径，并隐藏后台保活控制
- `POST /api/switch` 允许执行账号切换，切换会作用在这台电脑的默认认证文件上
- `POST /api/keepalive` 会直接返回 403，不能控制后台保活
- 公网页面仍可上传认证文件到指定仓库池账号，用来把另一台电脑下载到的最新默认认证同步回对应账号池

如果用 Cloudflare Tunnel 暴露本机服务，可以按这个形状配置：

```bash
cloudflared tunnel create codex-quota
cloudflared tunnel route dns codex-quota codex-quota.shizaishiwo.com
```

`~/.cloudflared/config.yml` 示例：

```yaml
tunnel: codex-quota
credentials-file: /Users/wangbin/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: codex-quota.shizaishiwo.com
    service: http://127.0.0.1:8765
  - service: http_status:404
```

启动：

```bash
cloudflared tunnel run codex-quota
```

如果使用 Nginx、Caddy 或其他反向代理，也要保留原始 `Host` 或设置 `X-Forwarded-Host`。如果需要公网切换账号，不要在代理层阻断 `POST /api/switch`；仍建议阻断 `POST /api/keepalive`，避免公网控制后台保活。也不要阻断 `POST /api/accounts/<id>/auth.json`，否则公网认证上传会不可用。

## 注意

这个项目不会把任何 `auth.json` 放进仓库。切换时生成的备份会放在本地 `backups/` 目录，并被 `.gitignore` 忽略。

一键切换会真正关闭并重新打开 macOS 的 Codex 桌面端应用。
