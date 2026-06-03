# Codex 多账号登录与保活说明

这份文档说明如何用不同的 `CODEX_HOME` 保存多个 Codex 登录环境，并让仓库池账号在后台保持运行。项目现在支持 macOS 和 Windows。

## 目录约定

默认账号目录：

```text
macOS:   /Users/wangbin/.codex
Windows: C:\Users\imgw\.codex
```

仓库池账号目录必须命名为 `.codex-账号id`，并且目录里有可用的 `auth.json`：

```text
macOS:   /Users/wangbin/.codex-riqu1/auth.json
Windows: C:\Users\imgw\.codex-riqu1\auth.json
```

网页端会自动扫描当前用户 home 下所有 `.codex-*` 目录。也可以用环境变量指定扫描根目录：

```bash
CODEX_ACCOUNT_SEARCH_ROOT=/Users/wangbin python app.py
```

```powershell
$env:CODEX_ACCOUNT_SEARCH_ROOT = "C:\Users\imgw"
python app.py
```

## 1. 新建独立 Codex Home 并登录

macOS:

```bash
mkdir -p ~/.codex-riqu1
CODEX_HOME=$HOME/.codex-riqu1 codex login
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\.codex-riqu1"
$env:CODEX_HOME = "$HOME\.codex-riqu1"
codex login
```

登录完成后确认存在：

```text
C:\Users\imgw\.codex-riqu1\auth.json
```

## 2. 启动网页端

默认地址：

```text
http://127.0.0.1:8765
```

macOS:

```bash
python app.py
```

Windows PowerShell:

```powershell
$env:CODEX_ACCOUNT_SEARCH_ROOT = "C:\Users\imgw"
$env:CODEX_SWITCHER_PORT = "8765"
python app.py
```

端口可以改，例如：

```powershell
$env:CODEX_SWITCHER_PORT = "9876"
python app.py
```

然后打开：

```text
http://127.0.0.1:9876
```

## 3. macOS 后台保活

安装并检查 `tmux`：

```bash
brew install tmux
tmux -V
```

手动启动指定账号：

```bash
tmux new -s codex-riqu1
export CODEX_HOME=$HOME/.codex-riqu1
codex
```

后台挂起当前会话：

```text
Ctrl-b 然后按 d
```

重新进入：

```bash
tmux attach -t codex-riqu1
```

查看所有会话：

```bash
tmux list-sessions
```

自动扫描并启动所有 `.codex-*` 仓库池账号：

```bash
bash scripts/ensure_codex_keepalive.sh
```

## 4. Windows 后台保活

Windows 使用 PowerShell 脚本：

```powershell
Set-Location "C:\path\to\codex-account-switcher"
powershell -ExecutionPolicy Bypass -File .\scripts\ensure_codex_keepalive_windows.ps1
```

按你的 Windows 用户目录显式扫描：

```powershell
Set-Location "C:\path\to\codex-account-switcher"
powershell -ExecutionPolicy Bypass -File .\scripts\ensure_codex_keepalive_windows.ps1 -AccountSearchRoot "C:\Users\imgw"
```

同时启动本地网页端检测接口：

```powershell
Set-Location "C:\path\to\codex-account-switcher"
powershell -ExecutionPolicy Bypass -File .\scripts\ensure_codex_keepalive_windows.ps1 -AccountSearchRoot "C:\Users\imgw" -StartWeb -Port 8765
```

修改网页端口：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ensure_codex_keepalive_windows.ps1 -AccountSearchRoot "C:\Users\imgw" -StartWeb -Port 9876
```

脚本会：

- 扫描 `C:\Users\imgw\.codex-*`
- 跳过缺失或明显无效的 `auth.json`
- 给每个账号写入 trusted 项目配置
- 为每个允许保活的账号启动独立 PowerShell 窗口
- 可选启动网页端 `http://127.0.0.1:<端口>`

日志位置：

```text
logs\codex-keepalive-windows.log
```

PID 状态文件：

```text
keepalive_windows_pids.json
```

## 5. 网页端保活控制

网页端每个仓库池账号都有后台保活模式：

- `自动`：当前不会因为 `1周` 额度为 0 自动暂停，启动脚本会启动所有未手动停止的 `.codex-*` 账号。
- `启动`：手动强制启动后台保活。
- `停止`：手动停止保活，并阻止下一轮脚本自动拉起。

保活状态保存在：

```text
keepalive_state.json
```

## 6. 注意

- 不要把任何真实 `auth.json` 提交到仓库。
- 自动测试或联调时不要调用账号切换接口。
- Windows 默认账号路径是 `C:\Users\imgw\.codex\auth.json`；如果当前 Windows 用户不是 `imgw`，项目会按当前 `$HOME` 自动推导。
- 如需固定扫描目录，设置 `CODEX_ACCOUNT_SEARCH_ROOT`。
