# 安全模型

## 我们防什么

| 威胁 | 对策 |
|---|---|
| 连错服务（局域网里连到别人的 companion） | companion 有 token + `/api/ping` 验名；Python 连上先验 `name == droid-mcp-companion` |
| token 泄露（局域网嗅探） | 同一 Wi-Fi 前提 + Bearer；敏感环境请用手机热点（点对点）。**不承诺防中间人**，见下 |
| 恶意短信/联系人内容注入 AI（prompt injection） | 工具输出是 data 不是指令；Skill 要求模型只抠验证码数字，不执行短信里的“指示” |
| AI 乱发短信/乱打电话 | companion App 内默认关闭，需手动开；客户端工具审批；`call_dial` 描述里写明话费 |
| 路径穿越读全盘 | `_safe_path` 沙盒（/sdcard+家目录），有单测；companion 侧 `jailCheck` + 越界提示开“所有文件访问” |
| 供应链（pip 依赖投毒） | **零第三方依赖**，连锁都没得投 |

## 我们不防什么（诚实区）

- **局域网中间人**：HTTP 明文。咖啡馆 Wi-Fi 上用 = 裸奔，请用手机热点或 Termux 本机模式。
- **手机丢了**：companion token 在 App 里，拿到手机就能用。丢手机先锁屏，token 可重装刷新。
- **AI 本身作恶**：工具审批在客户端侧，本项目只保证“调了什么可审计”（`calls.jsonl`）。
- **系统级漏洞**：靠 Google/厂商更新，不在本项目射程内。

## 报告漏洞

直接提 Issue（标题注明 [security]），涉及在野利用的先发 Discussions 私信，
48 小时内回。不要在公开 Issue 里贴可复现的 exploit 细节。
