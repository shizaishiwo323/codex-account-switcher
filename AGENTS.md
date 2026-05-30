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

- `GET /api/accounts`：通过 `config.py` 动态扫描账号目录，并发查询各账号额度。
- `POST /api/switch`：根据账号 id 切换当前默认账号。
- `GET /api/accounts/<id>/auth.json`：下载指定账号的认证文件。
- `POST /api/accounts/<id>/auth.json`：上传认证文件并覆盖指定仓库池账号，覆盖前会先比对和备份。
- `POST /api/keepalive`：设置某个仓库池账号的后台保活模式：`auto`、`on`、`off`。
- `/`：提供 `static/index.html` 前端页面。

本地接口和公网接口的功能应保持一致，只有一个区别：公网接口不能点击切换账号，也不能控制后台保活，只有本地接口可以执行这些本机动作。除账号切换按钮、切换能力、保活控制能力外，公网端应保留和本地端一致的账号展示、额度查询、刷新、认证下载、认证上传等其他功能。

账号切换会：

1. 校验目标账号和默认账号的 `auth.json`。
2. 读取默认认证的 `account_id`，在账号池中找到当前默认认证实际对应的原账号 A。
3. 比对默认认证文件和 A 账号池里的认证文件；如果不同，说明默认认证更新过，需要先把默认认证回写覆盖到 A 账号池。
4. 回写前必须同时备份两边文件：默认认证当前文件、A 账号池旧文件。备份文件名要带操作类型、角色、账号 id 和时间戳，能看出哪个是哪个。
5. 备份即将被目标账号覆盖的默认认证文件。这个备份名必须体现账号流向，例如 `before_switch-账号A-to-账号B`，不能只写 `default`，否则用户无法看出是从哪个账号切到哪个账号。
6. 关闭 Codex 桌面端。
7. 用目标账号 B 的 `auth.json` 覆盖默认认证文件。
8. 重新打开 Codex 桌面端。

认证上传会：

1. 只允许覆盖仓库池账号的 `auth.json`，不允许远程上传覆盖默认配置。
2. 校验上传文件是可读取的 Codex/Hermes `auth.json`。
3. 比对上传文件和目标账号池当前认证文件；如果完全相同，不覆盖也不创建备份。
4. 如果不同，先备份目标账号池旧文件和本次上传文件，再用上传文件覆盖目标账号池认证。
5. 备份文件必须放在 `backups/`，文件名要能区分 `target_before_upload` 和 `uploaded_auth`。

经验记录：下载认证通常用于跨电脑同步。比如另一台电脑下载的是“默认配置”的认证文件，但那台电脑当时实际登录的是 A 账号，那么上传时应提示用户把这个文件上传到 A 账号卡片，而不是上传到下载按钮所在机器的默认配置。

## 账号发现

网站/API 端会自动扫描 `/Users/wangbin` 下名字形如 `.codex-*` 且包含 `auth.json` 的目录。目录名去掉 `.codex-` 后就是账号 id，例如：

```text
/Users/wangbin/.codex-shizaishiwo0/auth.json -> shizaishiwo0
/Users/wangbin/.codex-zshi0509/auth.json -> zshi0509
```

默认账号是 `/Users/wangbin/.codex/auth.json`，`can_switch` 为 `False`。自动发现的 `.codex-*` 账号默认 `can_switch` 为 `True`。

仓库池账号目录需要提前完成 Codex 登录，并保证目录里存在可用的 `auth.json`。

如果需要自定义显示名或切换能力，只在 `config.py` 的 `ACCOUNT_OVERRIDES` 中新增覆盖项，不要重新维护完整静态账号列表。

## 新增账号方式

以后用户可能会不定期增加新的账号。新增账号时只需要创建新的 `.codex-账号id` 目录并完成登录：

```bash
mkdir -p ~/.codex-zshi0509
CODEX_HOME=$HOME/.codex-zshi0509 codex login
```

网页/API 和 `scripts/ensure_codex_keepalive.sh` 会自动识别这个目录，不需要手动把账号同步到两个地方。新增后建议运行：

```bash
python app.py
```

并打开 `http://127.0.0.1:8765` 检查页面是否能显示新账号。也可以直接运行：

```bash
bash scripts/ensure_codex_keepalive.sh
```

确认保活脚本能识别并启动新账号对应的 tmux session。

## 后台保活控制

网页端每个仓库池账号都有后台保活控制：

- `auto`：默认模式。当前不会因为 `1周` 额度为 0 自动暂停，开机脚本会启动所有未手动停止的 `.codex-*` 账号。
- `on`：手动强制保活，即使周额度为 0 也会启动。
- `off`：手动停止保活，并阻止 launchd 下一轮重新拉起。

保活状态保存在 `keepalive_state.json`，该文件是运行状态，不提交仓库。按 `1周` 窗口自动暂停的代码开关目前关闭；以后恢复时必须按 `1周` 窗口判断，不要按 `5小时` 窗口判断。

## 本地运行

如果没有特别说明，运行 Python 默认使用 conda 的 base 环境。

```bash
python app.py
```

## 重要约束

禁止批量删除文件或目录。

自动测试或联调时，不允许自动点击或调用账号切换配置功能，包括页面上的切换按钮和 `POST /api/switch`。账号切换只能由用户人工测试。

自动测试或联调认证上传时，不要使用真实 `auth.json`。只允许用临时目录里的假认证文件或单元测试夹具验证上传、比对、备份逻辑。

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
- 修改账号列表、账号切换、认证下载/上传、后台保活后，优先检查 `README.md`、`MULTI_ACCOUNT_KEEPALIVE.md`、`CODEX_KEEPALIVE_LAUNCHD.md` 是否也需要同步说明。
