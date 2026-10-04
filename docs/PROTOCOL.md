# droid-mcp companion 协议 v1

companion 是一个跑在手机上的 APK：一个前台服务 + 手写 HTTP（无第三方库），
把手机能力变成局域网 API。这样**没装 Termux 的手机也能用 droid-mcp**——
Python 端切到 companion 后端即可，MCP 那头没有任何变化。

```
AI 客户端 --stdio/MCP--> droid_mcp.py --HTTP/局域网--> companion APK（手机）
```

## 连接

- 地址：`http://<手机局域网 IP>:4833`（端口写死，避免扫端口灰色用途）
- 鉴权：首次启动 App 显示 token（16 位），以后存在手机里。
  每个请求带 `?token=xxx` 或头 `Authorization: Bearer xxx`。
  错了回 `{"ok": false, "error": "no_token"}`。
- 发现：`GET /api/ping` → `{"ok": true, "data": {"name": "droid-mcp-companion", "version": "0.2.0"}}`
  Python 端连上先 ping，名字不对就拒绝（防连到别人的服务上）。

##  envelop

成功：`{"ok": true, "data": <任意 JSON>}`
失败：`{"ok": false, "error": "<机器可读码>"}`
`error` 取值：`no_token` / `denied`（系统权限没给，data 里写去哪开）/
`bad_args` / `unavailable`（这台手机不支持）。

读用 GET（参数走 query），写用 POST（JSON body）。

## 端点（与 MCP 工具名一一对应）

| 方法与路径 | 参数 | 说明 |
|---|---|---|
| GET `/api/device/info` | – | 厂商/机型/安卓版本 |
| GET `/api/battery` | – | 电量/充电/健康度/温度 |
| GET `/api/sms/inbox` | `limit`（默认 20）、`offset` | 短信收件箱 |
| POST `/api/sms/send` | `to`、`body` | 发短信（要 SEND_SMS 权限） |
| GET `/api/call/log` | `limit`（默认 20） | 通话记录 |
| POST `/api/call/dial` | `number` | 直接拨号（ACTION_CALL，要权限，非确认框） |
| GET `/api/contacts` | – | 通讯录 |
| GET `/api/clipboard/get` | – | 剪贴板 |
| POST `/api/clipboard/set` | `text` | 写剪贴板 |
| POST `/api/notify` | `title?`、`content`、`id?` | 发通知 |
| POST `/api/notification/remove` | `id` | 撤通知 |
| POST `/api/toast` | `text` | Toast |
| POST `/api/vibrate` | `ms?`（默认 100） | 震动 |
| GET `/api/wifi` | – | 当前 Wi-Fi |
| GET `/api/location` | `provider?`（gps/network，默认 network） | 定位 |
| GET `/api/storage/list` | `path`（默认 Download 目录） | 列目录 |
| GET `/api/storage/read` | `path`、`max_bytes?`（默认 64KB） | 读文本文件 |
| POST `/api/storage/write` | `path`、`text`、`overwrite?`（默认 false） | 写文本文件 |
| GET `/api/apps` | – | 已安装应用（包名+名称，不含系统隐藏项） |
| POST `/api/apps/launch` | `package` | 启动应用 |

不在表里的（如截屏/相机/传感器）：v1 companion 不做，用 Termux 后端。
Python 端调到 companion 不支持的工具时，报“切 Termux 后端或等后续版本”，不撒谎。

## 安全边界（写进 App 介绍页，原话）

1. 只监听局域网，不打洞、不上云，关 App 即关服务。
2. token 在手机屏幕上，你扫一眼告诉 AI，一机一 token。
3. 发短信/拨号是真金白银的操作：App 内默认关闭，需手动开开关（`/api/sms/send`、`/api/call/dial` 没开时回 `denied`）。
4. 完整 /sdcard 访问要手动去设置里开“所有文件访问权限”，否则 storage 只给 Download 和 App 目录。
