# Windows 版 Codex 多账号登录与保活说明

本说明对应 Windows 用户目录：

```text
C:\Users\imgw\.codex
```

如果 Windows 用户名不是 `imgw`，把命令里的 `C:\Users\imgw` 换成你的实际用户目录即可。

## 1. 默认账号和仓库池账号

默认账号：

```text
C:\Users\imgw\.codex\auth.json
```

仓库池账号：

```text
C:\Users\imgw\.codex-riqu1\auth.json
C:\Users\imgw\.codex-zshi0509\auth.json
```

网页端会扫描 `C:\Users\imgw` 下所有 `.codex-*` 目录，并把目录名去掉 `.codex-` 后作为账号 id。

## 2. 新建账号并登录

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\imgw\.codex-riqu1"
$env:CODEX_HOME = "C:\Users\imgw\.codex-riqu1"
codex login
```

登录后确认：

```powershell
Test-Path "C:\Users\imgw\.codex-riqu1\auth.json"
```

## 3. 启动网页端

```powershell
Set-Location "C:\path\to\codex-account-switcher"
$env:CODEX_ACCOUNT_SEARCH_ROOT = "C:\Users\imgw"
$env:CODEX_SWITCHER_PORT = "8765"
python app.py
```

打开：

```text
http://127.0.0.1:8765
```

修改端口：

```powershell
$env:CODEX_SWITCHER_PORT = "9876"
python app.py
```

## 4. 启动保活脚本

只启动保活：

```powershell
Set-Location "C:\path\to\codex-account-switcher"
powershell -ExecutionPolicy Bypass -File .\scripts\ensure_codex_keepalive_windows.ps1 -AccountSearchRoot "C:\Users\imgw"
```

启动保活，同时启动网页端检测接口：

```powershell
Set-Location "C:\path\to\codex-account-switcher"
powershell -ExecutionPolicy Bypass -File .\scripts\ensure_codex_keepalive_windows.ps1 -AccountSearchRoot "C:\Users\imgw" -StartWeb -Port 8765
```

换端口：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ensure_codex_keepalive_windows.ps1 -AccountSearchRoot "C:\Users\imgw" -StartWeb -Port 9876
```

## 5. 脚本会做什么

- 扫描 `C:\Users\imgw\.codex-*`
- 跳过缺少 `auth.json` 的目录
- 跳过明显不可用的认证文件
- 写入 trusted 项目配置
- 为每个仓库池账号启动独立 PowerShell 窗口运行 Codex
- 使用 `keepalive_state.json` 尊重网页端的 `自动`、`启动`、`停止` 设置

## 6. 日志和状态

日志：

```text
logs\codex-keepalive-windows.log
```

保活 PID 状态：

```text
keepalive_windows_pids.json
```

网页端保活状态：

```text
keepalive_state.json
```
