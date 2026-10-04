# 架构

```
                    ┌─────────────┐  stdio/NDJSON   ┌──────────────┐
                    │  AI 客户端   │ ────────────── │ droid_mcp.py │
                    │ Claude Code │  或 HTTP /mcp  │  (MCP server) │
                    │ OpenCode…   │                └──────┬───────┘
                    └─────────────┘                       │ 后端三选一
              ┌──────────────┐                            │
              │ console.py   │── 同一台机器 ── import ────┤
              │ (网页管家)   │   审计日志(calls.jsonl)     │
              └──────────────┘                            ├── termux 后端 ── termux-* ── 手机系统
                                                         ├── companion 后端 ── HTTP ── companion APK
                                                         └── mock 后端 ── 假数据（测试/演示）
```

## 为什么是这个形状

- **MCP server 本体是单文件**（`droid_mcp.py`）：协议层（`handle()`）与工具层
  （`t_*` 函数）彻底分开，加工具 = 加一个函数 + 注册表一行 + mock 数据。
- **后端是接口**（`Backend` 基类）：`tx()` 跑 termux 命令，`hx()` 调 companion
  HTTP。工具实现里按后端类型分支，互不知晓对方存在。
- **console 是另一个进程**：它 `import droid_mcp` 复用同一套工具与后端，
  通过 `calls.jsonl` 审计日志看到 server 的调用（不记参数内容，短信不落盘）。
- **companion 是独立仓库级模块**（`companion/`）：完整 Gradle App，
  与 Python 端只通过 `docs/PROTOCOL.md` 契约耦合。改契约先改文档。
- **Skill 是分发层**（`skills/`）：把“怎么用好手机工具”的知识打包，
  跟着 Claude Code / OpenCode 的 Skill 机制走，不用每次口头教 AI。

## 数据流（以找验证码为例）

1. 客户端 `tools/call sms_inbox` → server 选后端 → termux/companion 取短信
2. 结果包成 MCP content 回去；调用元数据（工具名/成败/耗时）进 `calls.jsonl`
3. console 轮询展示；`clipboard_set` 同理把验证码塞回手机

## 加新东西的入口

| 想加 | 改哪 |
|---|---|
| 新工具 | `droid_mcp.py`（实现+注册+mock）+ `test_droid_mcp.py` 用例 + `--dump-tools-md` 刷文档 |
| 新后端 | 子类化 `Backend`，实现 `tx/hx` 中用到的那个 |
| companion 端点 | 先改 `docs/PROTOCOL.md`，再改 `companion/.../Api.java`，Python 侧加映射 |
| 新客户端配置 | README 客户端配置节 |
