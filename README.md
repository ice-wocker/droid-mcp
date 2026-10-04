# droid-mcp 📱

[![CI](https://github.com/ice-wocker/droid-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ice-wocker/droid-mcp/actions/workflows/ci.yml)
[![Companion APK](https://github.com/ice-wocker/droid-mcp/actions/workflows/companion.yml/badge.svg)](https://github.com/ice-wocker/droid-mcp/actions/workflows/companion.yml)
[![GitHub stars](https://img.shields.io/github/stars/ice-wocker/droid-mcp?style=social)](https://github.com/ice-wocker/droid-mcp/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](droid_mcp.py)

**Your Android phone as MCP tools: 47 tools, 3 backends, 1 file.**

**你的安卓手机，变成 MCP 工具：47 个工具，3 种接法，1 个文件。**

如果觉得有用，点个 ⭐ 吧！

## 30 秒上手（三选一）

**A. 手机 Termux 里跑（功能最全，47/47）**

```bash
pkg install termux-api python git && git clone https://github.com/ice-wocker/droid-mcp.git
cd droid-mcp && claude mcp add droid-mcp -- python3 $(pwd)/droid_mcp.py
```

**B. companion APK（不用装 Termux，20/47，数据类全覆盖）**

去 [Releases](https://github.com/ice-wocker/droid-mcp/releases) 下 companion APK，
手机上打开，允许要的权限，屏幕上有 token 和 IP，然后：

```bash
claude mcp add droid-mcp -- python3 droid_mcp.py \
  --backend companion --companion http://192.168.1.5:4833 --token 屏幕上那串
```

详细步骤与各厂商权限在哪开：[`docs/COMPANION.md`](docs/COMPANION.md)。

**C. 先玩起来（无手机，47/47 全是假数据）**

```bash
python3 droid_mcp.py --mock
```

然后直接跟 AI 说话：

```
你：刚注册的那个网站，短信验证码多少？
AI：● sms_inbox
    482916（MockPay，5 分钟内有效）。要我帮你填进剪贴板吗？
你：帮我录 10 秒备忘，再弹个通知提醒我听
AI：● mic_record → /sdcard/Download/droid-mcp-rec.m4a
    ● notify → 已发通知。
```

## 兼容矩阵（核心）

`--backend auto`（默认）会自动选：有 `termux-*` 就用 Termux，否则看有没有给
`--companion`，都没有就报错指路（exit 2，三选一指南直接打到 stderr）。

| 工具 | 干嘛 | termux | companion | mock |
|---|---|---|---|---|
| `device_info` | 厂商/机型/安卓版本 | ✅ | ✅ | ✅ |
| `battery` | 电量/充电/健康度/温度 | ✅ | ✅ | ✅ |
| `sms_inbox` | 读短信（找验证码） | ✅ | ✅ | ✅ |
| `sms_send` ✏️ | 发短信（companion 内默认关，需手动开） | ✅ | ✅ | ✅ |
| `call_log` | 通话记录 | ✅ | ✅ | ✅ |
| `call_dial` ✏️ | 直接拨号（会产生话费） | ✅ | ✅ | ✅ |
| `contacts` | 通讯录 | ✅ | ✅ | ✅ |
| `clipboard_get` | 读剪贴板 | ✅ | ✅ | ✅ |
| `clipboard_set` ✏️ | 写剪贴板 | ✅ | ✅ | ✅ |
| `notify` ✏️ | 发系统通知 | ✅ | ✅ | ✅ |
| `notification_remove` ✏️ | 撤通知 | ✅ | ✅ | ✅ |
| `notification_list` | 通知栏都有啥 | ✅ | ❌ | ✅ |
| `toast` ✏️ | 底部小提示 | ✅ | ✅ | ✅ |
| `vibrate` ✏️ | 震动 | ✅ | ✅ | ✅ |
| `torch` ✏️ | 手电筒 | ✅ | ❌ | ✅ |
| `brightness_set` ✏️ | 屏幕亮度 | ✅ | ❌ | ✅ |
| `volume_set` ✏️ | 调音量 | ✅ | ❌ | ✅ |
| `wallpaper_set` ✏️ | 换壁纸 | ✅ | ❌ | ✅ |
| `media_scan` ✏️ | 扫文件进图库 | ✅ | ❌ | ✅ |
| `media_play` ✏️ | 放音频 | ✅ | ❌ | ✅ |
| `camera_photo` ✏️ | 拍照（回路径，省 token） | ✅ | ❌ | ✅ |
| `mic_record` ✏️ | 录音（回路径） | ✅ | ❌ | ✅ |
| `tts_speak` ✏️ | 手机开口说话 | ✅ | ❌ | ✅ |
| `tts_engines` | TTS 引擎列表 | ✅ | ❌ | ✅ |
| `screenshot` | 截屏（小图内嵌，大图给路径） | ✅ | ❌ | ✅ |
| `location` | 定位（network 快/gps 准） | ✅ | ✅ | ✅ |
| `wifi_status` | 当前 Wi-Fi | ✅ | ✅ | ✅ |
| `wifi_scan` | 扫周围 Wi-Fi（要开定位开关） | ✅ | ❌ | ✅ |
| `wifi_toggle` ✏️ | Wi-Fi 开关 | ✅ | ❌ | ✅ |
| `sensor_list` | 有哪些传感器 | ✅ | ❌ | ✅ |
| `sensor_read` | 读传感器（机器人眼睛） | ✅ | ❌ | ✅ |
| `audio_info` | 音频系统信息 | ✅ | ❌ | ✅ |
| `camera_info` | 摄像头列表 | ✅ | ❌ | ✅ |
| `cell_info` | 基站/信号 | ✅ | ❌ | ✅ |
| `storage_list` | 列手机目录（沙盒内） | ✅ | ✅ | ✅ |
| `storage_read` | 读文本文件 | ✅ | ✅ | ✅ |
| `storage_write` ✏️ | 写文本文件（默认不覆盖） | ✅ | ✅ | ✅ |
| `share_file` ✏️ | 系统分享面板 | ✅ | ❌ | ✅ |
| `open_url` ✏️ | 浏览器打开链接 | ✅ | ❌ | ✅ |
| `confirm_dialog` ✏️ | 手机弹确认框等人点（human-in-the-loop） | ✅ | ❌ | ✅ |
| `app_launch` ✏️ | 启动 App（companion 给包名就行） | ⚠️ 要 activity | ✅ | ✅ |
| `app_list` | 已安装应用列表 | ❌ 要 root | ✅ | ✅ |
| `fingerprint_auth` ✏️ | 指纹/面容确认（最高级别人工确认） | ✅ | ❌ | ✅ |
| `voice_transcribe` | 语音转文字 | ✅ | ❌ | ✅ |
| `ir_blast` ✏️ | 红外发射（万能遥控器） | ✅ | ❌ | ✅ |
| `usb_list` | USB 口设备盘点 | ✅ | ❌ | ✅ |
| `media_info` | 当前播放状态 | ✅ | ❌ | ✅ |

✏️ = 写/动作类，`--read-only` 下从列表里消失；⚠️ = 部分支持（看格子里说明）。完整参数说明：[`docs/TOOLS.md`](docs/TOOLS.md)
（`python3 droid_mcp.py --dump-tools-md` 生成，保证文档和代码永远一致）。
companion 的 HTTP 契约：[`docs/PROTOCOL.md`](docs/PROTOCOL.md)。

## 为什么是 droid-mcp？

|  | ADB / scrcpy 方案 | Tasker 方案 | droid-mcp |
|---|---|---|---|
| AI 直接用 | ❌ 人肉中转 | ❌ 配 HTTP 插件 | ✅ MCP 原生 |
| 不装 Termux 能用吗 | 要配 adb | 要买 App | ✅ companion APK |
| 依赖 | SDK 几百 MB | 付费+插件 | **1 个 py 文件 / 1 个 APK，0 第三方依赖** |
| 隐私 | 看你怎么搭 | 云端账号 | 全程本机/局域网，无云 |

## 隐私与安全模型

1. **没服务器**：短信/联系人/位置只在你手机内存里过一遍，进的是你自己的 AI 会话。
2. **局域网 + token**：companion 只监听 4833，不打洞；token 在手机屏幕上，一机一换。
3. **烧钱操作双保险**：`sms_send` / `call_dial` 在 companion App 内默认关闭（手动开开关），
   MCP 客户端侧还有工具审批（Claude Code 默认每次都问）。
4. **存储沙盒**：`storage_*` 只允许 /sdcard 与家目录，`../` 越狱会被拦（有单测）。
5. **mock 全是 555 虚构号段**，截图大了不内嵌。

## 客户端配置

```bash
# Claude Code
claude mcp add droid-mcp -- python3 /path/to/droid_mcp.py
# companion 版（示例 IP/token 换你自己的）
claude mcp add droid-mcp -- python3 /path/to/droid_mcp.py \
  --backend companion --companion http://192.168.1.5:4833 --token xxx
```

Claude Desktop / OpenCode 等 stdio 客户端：command=`python3`，args=`[/path/to/droid_mcp.py, ...]`，
flags 照抄上面。

## 手机在兜里，agent 在云端（HTTP 传输）

stdio 要求客户端和 server 同一台机器。手机在兜里、agent 跑云端时：

```bash
# 手机 Termux 里
python3 droid_mcp.py --http 0.0.0.0:4844
# 任意能连上手机的机器
curl -X POST http://手机IP:4844/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

`POST /mcp` 跑完整 JSON-RPC（`GET /health` 探活）。协议细节和 stdio 完全一致，
只是换了个信封——局域网用可以，公网请自己套 TLS（见 `docs/SECURITY.md` 诚实区）。

## 网页管家 + 官方 Skill

```bash
python3 console.py   # → http://127.0.0.1:4855
```

状态、47 个工具表、实时调用日志、在线试跑，一个页面全齐。
调用只记工具名/成败/耗时（`~/.droid-mcp/calls.jsonl`），参数内容不落盘。

`skills/phone-assistant/SKILL.md` 是喂给 AI 的“手机使用手册”：
验证码流程、烧钱操作 double-check、隐私红线。Claude Code / OpenCode
放到 skills 目录即生效，不用每次口头教。

## 常见坑（先看这节，能省一小时）

| 症状 | 原因 | 解法 |
|---|---|---|
| `termux-* 空输出/超时` | 没给 Termux:API 授权，或手机息屏 | 亮屏，手机上打开 Termux:API 点授权 |
| `companion 说不：denied` | 系统权限/开关没开 | 看 App 里那行字写去哪开，见 `docs/COMPANION.md` 厂商表 |
| `gps 定位半天不出` | 物理规律，室内搜不到星 | 先用 network；gps 去窗边 |
| `wifi_scan 空` | 安卓要求开定位开关才给扫 | 设置里打开定位（不用开 gps 精度） |
| `screenshot 不可用` | 旧版 Termux:API 没这个命令 | 升级 Termux:API，或用 camera_photo |
| 小米/MIUI 收不到通知 | MIUI 杀后台 | 锁后台 + 自启动，见厂商表 |
| 华为没 Termux:API 用 | —— | 直接用 companion APK（就是为这个生的） |

## 开发

```bash
pip install pytest && pytest -q   # 12 用例，mock 模式，无需真机
```

加新工具三件套：`droid_mcp.py` 里加实现 + 注册表 + mock 数据，`test_droid_mcp.py` 加用例，
`docs/TOOLS.md` 用 `--dump-tools-md` 重新生成。改协议先改 `docs/PROTOCOL.md`。

版本历史：[CHANGELOG.md](CHANGELOG.md)。

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ice-wocker/droid-mcp&type=Date)](https://star-history.com/#ice-wocker/droid-mcp&Date)

## License

MIT — 见 [LICENSE](LICENSE)。
