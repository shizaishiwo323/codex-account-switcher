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
Path("/Users/wangbin/.codex-shizaishiwo123/auth.json")
```

## 运行

```bash
python app.py
```

然后打开：

```text
http://127.0.0.1:8765
```

## 注意

这个项目不会把任何 `auth.json` 放进仓库。切换时生成的备份会放在本地 `backups/` 目录，并被 `.gitignore` 忽略。

一键切换会真正关闭并重新打开 macOS 的 Codex 桌面端应用。
