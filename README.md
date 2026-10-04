# droid-mcp 📱

[![CI](https://github.com/ice-wocker/droid-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ice-wocker/droid-mcp/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/ice-wocker/droid-mcp?style=social)](https://github.com/ice-wocker/droid-mcp/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](droid_mcp.py)

**Your Android phone as MCP tools. One stdlib-only Python file, any MCP client.**

**你的安卓手机，变成 MCP 工具。一个纯标准库 Python 文件，任意 MCP 客户端即插即用。**

如果觉得有用，点个 ⭐ 吧！

## 30 秒上手

手机上装好 Termux + Termux:API（`pkg install termux-api`），然后：

```bash
git clone https://github.com/ice-wocker/droid-mcp.git && cd droid-mcp

# Claude Code 一行接入
claude mcp add droid-mcp -- python3 $(pwd)/droid_mcp.py
```

然后直接跟 AI 说话：

```
你：刚注册的那个网站，短信验证码多少？
AI：● sms_inbox
    482916（MockPay，5 分钟内有效）。要我帮你填吗？
你：顺手弹个通知提醒我 10 分钟后看邮箱
AI：● notify
    已发通知。
```

没手机在手边？`--mock` 先玩起来（CI 也是这么测的）：

```bash
python3 droid_mcp.py --mock
```

## 12 个工具

| 工具 | 干嘛 | 写操作 |
|---|---|---|
| `device_info` | 机型/安卓版本，先调它确认连的是哪台手机 | – |
| `battery` | 电量/充电/健康度/温度 | – |
| `sms_inbox` | 读短信（找验证码的主力），`limit/offset` | – |
| `call_log` | 通话记录 | – |
| `contacts` | 通讯录 | – |
| `clipboard_get` | 读手机剪贴板 | – |
| `clipboard_set` | 写手机剪贴板（验证码直达剪贴板） | ✅ |
| `notify` | 发系统通知（“跑完了叫我”） | ✅ |
| `toast` | 底部小提示 | ✅ |
| `screenshot` | 截屏（小图内嵌回传，大图给路径） | – |
| `location` | 定位（network 快 / gps 准） | – |
| `wifi_status` | 当前 Wi-Fi（SSID/信号/速率） | – |

 paranoid → `droid_mcp.py --read-only`：写入类工具直接从列表里消失，调也调不动。

## 为什么是 droid-mcp？

|  | ADB / scrcpy 方案 | Tasker 方案 | droid-mcp |
|---|---|---|---|
| AI 直接用 | ❌ 要人肉中转 | ❌ 要配 HTTP 插件 | ✅ MCP 原生，Claude Code 零配置消费 |
| 依赖 | 电脑+数据线/配对 | 付费 App+插件 | Termux + 免费的 Termux:API |
| 体积 | SDK 几百 MB | 重 | **1 个文件，0 第三方依赖** |
| 隐私 | 取决于你怎么搭 | 云端账号 | 全程本机/局域网，无云 |

## 隐私

- 短信/联系人/位置只在**你的手机内存里**过一遍，进的是**你自己的** AI 会话，不经过本项目任何服务器（本项目就没有服务器）。
- 实在不放心：`--read-only` + 客户端侧的工具审批（Claude Code 默认每次都问你）。
- `--mock` 里的演示数据全是 555 虚构号段。

## 客户端配置

<details>
<summary>Claude Code（CLI，一行）</summary>

```bash
claude mcp add droid-mcp -- python3 /path/to/droid_mcp.py
# 只读版：claude mcp add droid-mcp-ro -- python3 /path/to/droid_mcp.py --read-only
```

</details>

<details>
<summary>Claude Desktop / 任意 stdio 客户端（JSON）</summary>

```json
{
  "mcpServers": {
    "droid-mcp": {
      "command": "python3",
      "args": ["/path/to/droid_mcp.py"]
    }
  }
}
```

</details>

<details>
<summary>OpenCode</summary>

OpenCode 配 MCP（`opencode.json`）：

```jsonc
{
  "mcp": {
    "droid-mcp": {
      "type": "local",
      "command": ["python3", "/path/to/droid_mcp.py"]
    }
  }
}
```

</details>

## 要求

- 手机：Termux + Termux:API App（`pkg install termux-api`），并给短信/联系人/定位授权
- 跑 server 这端：Python >= 3.10（跑在手机 Termux 里就行，也可以跑在同一局域网的电脑上——stdio 模式需要跟客户端同机，远程场景用 SSH 管道）
- 开发/测试：`pip install pytest`，`pytest` 全绿（10 用例，mock 模式，无需真机）

## 结构（就这几个文件）

```
droid_mcp.py       单文件 server：MCP(stdio/NDJSON) + 12 工具 + mock/只读模式
test_droid_mcp.py  10 个 pytest：握手/工具列表/mock 调用/只读/无 API 降级
.github/workflows/ci.yml  3.10–3.13 全绿
```

## 已知限制（诚实区）

- `screenshot` 要新版 Termux:API，旧版没有这个命令会明确报错（不装死）。
- `location` 的 gps 室内慢是物理规律，默认走 network。
- 部分国产 ROM 的短信/后台授权很作妖，报错信息里写了去哪开。

## Contributing

欢迎 PR / Issue，中英文都行。改工具先跑 `pytest`；加新工具请同时加 mock 数据 + 一个用例。

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ice-wocker/droid-mcp&type=Date)](https://star-history.com/#ice-wocker/droid-mcp&Date)

## License

MIT — 见 [LICENSE](LICENSE)。
