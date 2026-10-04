# Changelog

## v0.3.0（2026-10-04）—— 生态版

- 工具 40 → **47 个**：应用启动/列表、指纹确认、语音转写、红外、USB、播放状态
- **HTTP 传输**：`--http` 跑 MCP over POST，手机在兜里、agent 在云端
- **console.py 网页管家**：状态/工具表/实时日志/在线试跑（调用审计存 `calls.jsonl`，不记参数）
- **官方 Skill**：`skills/phone-assistant/`，验证码/烧钱操作/隐私红线一次写好
- companion APK 加 `/api/apps/launch`（21 端点）+ `QUERY_ALL_PACKAGES`
- 文档：`README_EN.md`、`docs/ARCHITECTURE.md`、`docs/SECURITY.md`（含“不防什么”诚实区）
- 修：companion 支持矩阵曾有 17 个工具误标 ✅（加回归测试锁死）

## v0.2.0（2026-10-04）—— 10 倍版

- 工具 12 → **40 个**：短信/电话/剪贴板/通知/相机/麦克风/TTS/传感器/文件/分享/确认框……
- **companion APK**：不装 Termux 也能用（局域网 HTTP + token，20 个数据类端点，见 `docs/PROTOCOL.md`）
- **三后端**：`termux`（40/40）/ `companion`（19/40）/ `mock`（40/40），auto 自动选，`--read-only` 一键只读
- 存储沙盒（只允许 /sdcard 与家目录）、参数校验（LLM 传错参只报 isError 不崩）
- 新增 `docs/COMPANION.md`（安装+厂商权限指南）、`docs/TOOLS.md`（40 工具表，`--dump-tools-md` 生成）

## v0.1.0（2026-10-04）

- 首版：单文件 MCP server，12 个工具，Termux + mock 双后端
