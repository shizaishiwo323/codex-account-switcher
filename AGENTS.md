# Codex Account Switcher 项目说明

本项目是一个本地 Codex 账号额度控制台，用来读取多个 Codex `auth.json`，展示每个账号的用量，并支持一键把某个账号切换为 Codex 桌面端当前使用的默认认证文件。

## 快速了解

- 运行入口：`app.py`
- 配置入口：`config.py`
- 前端页面：`static/index.html`、`static/script.js`、`static/style.css`
- 用量查询逻辑：`codex_usage.py`
- 开机自启动/保活脚本：`scripts/ensure_codex_keepalive.sh`
- launchd 配置：`launchd/com.shizaishiwo.codex-keepalive.plist`
- 本地访问地址：`http://127.0.0.1:8765`

## 工作方式

`app.py` 启动一个本地 HTTP 服务：

- `GET /api/accounts`：读取 `config.py` 里的 `ACCOUNTS`，并发查询各账号额度。
- `POST /api/switch`：根据账号 id 切换当前默认账号。
- `/`：提供 `static/index.html` 前端页面。

本地接口和公网接口的功能应保持一致，只有一个区别：公网接口不能点击切换账号，只有本地接口可以点击切换账号。除账号切换按钮/切换能力外，公网端应保留和本地端一致的账号展示、额度查询、刷新等其他功能。

账号切换会：

1. 校验目标账号和默认账号的 `auth.json`。
2. 关闭 Codex 桌面端。
3. 备份 `/Users/wangbin/.codex/auth.json` 到 `backups/`。
4. 用目标账号的 `auth.json` 覆盖默认认证文件。
5. 重新打开 Codex 桌面端。

## 账号配置

网站/API 端的账号列表在 `config.py` 的 `ACCOUNTS` 中维护。每个账号通常包含：

```python
{
    "id": "shizaishiwo0",
    "label": "仓库池 0",
    "auth_path": Path("/Users/wangbin/.codex-shizaishiwo0/auth.json"),
    "can_switch": True,
}
```

默认账号是 `/Users/wangbin/.codex/auth.json`，通常 `can_switch` 为 `False`。

仓库池账号目录需要提前完成 Codex 登录，并保证目录里存在可用的 `auth.json`。

## 新增账号时必须同步的位置

以后用户可能会不定期增加新的账号。当用户说要增加一个新账号时，需要同时同步到两个地方：

1. 网站/API 端：在 `config.py` 的 `ACCOUNTS` 中新增账号配置。
2. 开机自启动脚本端：在 `scripts/ensure_codex_keepalive.sh` 的 `ACCOUNTS` 数组中新增对应的 tmux session 和 `CODEX_HOME`。

两边的账号 id、显示名称、目录路径要保持一致或清晰对应。新增后建议运行：

```bash
python app.py
```

并打开 `http://127.0.0.1:8765` 检查页面是否能显示新账号。也可以直接运行：

```bash
bash scripts/ensure_codex_keepalive.sh
```

确认保活脚本能识别并启动新账号对应的 tmux session。

## 本地运行

如果没有特别说明，运行 Python 默认使用 conda 的 base 环境。

```bash
python app.py
```

## 重要约束

禁止批量删除文件或目录。

自动测试或联调时，不允许自动点击或调用账号切换配置功能，包括页面上的切换按钮和 `POST /api/switch`。账号切换只能由用户人工测试。

修复或修改项目文件后，需要重启正在运行的服务进程，确保服务加载的是最新代码，避免代码已改但运行中的服务仍是旧版本。

不要使用：

- `del /s`
- `rd /s`
- `rmdir /s`
- `Remove-Item -Recurse`
- `rm -rf`

需要删除文件时，只能一次删除一个明确路径的文件。

正确示例：

```powershell
Remove-Item "C:\path\to\file.txt"
```

如果需要批量删除文件，应停止操作，并请求用户手动删除。

## 注意事项

- 不要把任何真实 `auth.json` 提交到仓库。
- `backups/`、`logs/`、`server.log` 等运行产物通常不需要改动。
- 修改账号列表后，优先检查 `README.md`、`MULTI_ACCOUNT_KEEPALIVE.md`、`CODEX_KEEPALIVE_LAUNCHD.md` 是否也需要同步说明。
