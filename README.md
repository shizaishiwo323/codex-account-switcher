# Codex Account Switcher

本地网页端 Codex 账号额度控制台。它会读取多个 Codex `auth.json`，展示每个账号的 5 小时和 1 周剩余额度，并支持一键切换当前 Codex 桌面端使用的认证文件。

## 功能

- 查询默认账号和仓库池账号的 Codex 用量
- 显示账号邮箱、Plus/Plan、5 小时剩余额度、1 周剩余额度和重置时间
- 一键切换账号
- 切换时自动关闭 Codex 桌面端
- 切换前自动备份当前默认认证文件
- 覆盖 `/Users/wangbin/.codex/auth.json`
- 切换后重新打开 Codex 桌面端

## 默认账号路径

```python
DEFAULT_AUTH_PATH = Path("/Users/wangbin/.codex/auth.json")
```

## 仓库池路径

```python
Path("/Users/wangbin/.codex-shizaishiwo323/auth.json")
Path("/Users/wangbin/.codex-shizaishiwo0/auth.json")
Path("/Users/wangbin/.codex-shizaishiwo123/auth.json")
```

## 新增仓库池账号

在 `config.py` 的 `ACCOUNTS` 里新增一段即可：

```python
{
    "id": "shizaishiwo0",
    "label": "仓库池 0",
    "auth_path": Path("/Users/wangbin/.codex-shizaishiwo0/auth.json"),
    "can_switch": True,
}
```

要求是这个目录里已经存在登录好的 `auth.json`。

## 多账号登录与保活

如果需要用多个 `CODEX_HOME` 登录不同账号，并用 `tmux` 挂后台保活，见：

[MULTI_ACCOUNT_KEEPALIVE.md](MULTI_ACCOUNT_KEEPALIVE.md)

如果需要开机自动检测并挂起 3 个仓库池账号，见：

[CODEX_KEEPALIVE_LAUNCHD.md](CODEX_KEEPALIVE_LAUNCHD.md)

## 运行

```bash
python app.py
```

然后打开：

```text
http://127.0.0.1:8765
```

## 公网只读监控

建议使用子域名：

```text
codex-quota.shizaishiwo.com
```

`config.py` 里的 `PUBLIC_MONITOR_HOSTS` 已把这个域名配置为公网监控入口。请求 Host 命中该域名时：

- 前端只显示监控和刷新，不渲染切换按钮
- `/api/accounts` 会把所有账号标记为不可切换，并隐藏本机 `auth.json` 路径
- `POST /api/switch` 会直接返回 403，不能执行账号切换

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

如果使用 Nginx、Caddy 或其他反向代理，也要保留原始 `Host` 或设置 `X-Forwarded-Host`。建议在代理层额外阻断 `POST /api/switch`，让公网入口形成双保险。

## 注意

这个项目不会把任何 `auth.json` 放进仓库。切换时生成的备份会放在本地 `backups/` 目录，并被 `.gitignore` 忽略。

一键切换会真正关闭并重新打开 macOS 的 Codex 桌面端应用。
