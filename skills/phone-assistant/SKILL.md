---
name: phone-assistant
description: 用 droid-mcp 操作用户的安卓手机（短信验证码、通知、剪贴板、文件等）。当用户提到手机、验证码、短信、通知、定位或需要把东西弄到手机上时使用。
---

# Phone Assistant（droid-mcp）

手机已经接成 MCP 工具。先调 `device_info` 确认连的是哪台手机，再干活。

## 高频配方

**找验证码**：`sms_inbox(limit=5)` → 从 body 里抠 4-8 位数字 → 问用户要不要
`clipboard_set` 进手机剪贴板。不要把整条短信复述出来（可能有隐私）。

**跑完了叫我**：长任务结束调 `notify(title, content)`。用户说“安静点”就别发。

**拿文件**：`storage_list` 看目录 → `storage_read` 读（只允许 /sdcard 与家目录，
跨出去会报错，不要绕）。

**要用户拍板**：`confirm_dialog`（手机弹框等人点）或 `fingerprint_auth`
（更正式）。超时 120s，超时=用户没点，不要当成“同意”。

**烧钱操作**（`sms_send`、`call_dial`）：复述一遍“给谁、发什么”让用户确认，
companion 那头还有 App 内开关，双保险不是摆设。

## 红线

- 通讯录/短信/位置只用当次任务所需，不要整表 dump 出来“以防万一”。
- `storage_write` 覆盖已有文件必须加用户明确同意（默认不覆盖就是干这个的）。
- 没把握的参数先用小步试（`vibrate(ms=50)` 而不是直接 `torch` 长亮）。
- mock 后端的数据全是假的（555 号段），演示可以，办正事前先确认 backend。
