# droid-mcp 工具表（v0.2.0，由 --dump-tools-md 生成）

共 40 个工具（读 19 / 写 21）。companion 列是 companion APK v1 是否支持。

| 工具 | 写 | companion | 说明 |
|---|---|---|---|
| `device_info` | – | ✅ | 手机基本信息（厂商/机型/安卓版本） |
| `battery` | – | ✅ | 电池：电量/充电状态/健康度/温度 |
| `sms_inbox` | – | ✅ | 读短信收件箱 |
| `sms_send` | ✅ | ✅ | 发短信 |
| `call_log` | – | ✅ | 通话记录 |
| `call_dial` | ✅ | ✅ | 直接拨号（无确认框，会产生话费） |
| `contacts` | – | ✅ | 通讯录（姓名+号码） |
| `clipboard_get` | – | ✅ | 读手机剪贴板 |
| `clipboard_set` | ✅ | ✅ | 写手机剪贴板 |
| `notify` | ✅ | ✅ | 发系统通知 |
| `notification_remove` | ✅ | ✅ | 撤掉指定 id 的通知 |
| `notification_list` | – | ❌ | 当前通知栏里都有啥 |
| `toast` | ✅ | ✅ | 底部 Toast（一闪而过的小提示） |
| `vibrate` | ✅ | ✅ | 震动 |
| `torch` | ✅ | ✅ | 手电筒开关 |
| `brightness_set` | ✅ | ✅ | 屏幕亮度 1-255 |
| `volume_set` | ✅ | ✅ | 调音量 |
| `wallpaper_set` | ✅ | ✅ | 换壁纸（手机上的图片路径） |
| `media_scan` | ✅ | ✅ | 通知系统扫描文件（新照片/录音不出现在图库时用它） |
| `media_play` | ✅ | ✅ | 放一个音频文件 |
| `camera_photo` | ✅ | ✅ | 拍一张照片存手机上（回路径，不回图，省 token） |
| `mic_record` | ✅ | ✅ | 录音（回文件路径） |
| `tts_speak` | ✅ | ✅ | 手机开口说话（TTS） |
| `tts_engines` | – | ❌ | 可用的 TTS 引擎列表 |
| `screenshot` | – | ✅ | 截屏 |
| `location` | – | ✅ | 定位 |
| `wifi_status` | – | ✅ | 当前 Wi-Fi（SSID/信号/速率） |
| `wifi_scan` | – | ❌ | 扫描周围 Wi-Fi（要开定位开关，安卓规定的） |
| `wifi_toggle` | ✅ | ✅ | Wi-Fi 开关 |
| `sensor_list` | – | ❌ | 手机有哪些传感器 |
| `sensor_read` | – | ✅ | 读传感器（加速度/陀螺仪/光线…，做手机机器人必备） |
| `audio_info` | – | ❌ | 音频系统信息（有哪些输出流） |
| `camera_info` | – | ❌ | 摄像头列表（camera_photo 的 id 从这来） |
| `cell_info` | – | ❌ | 基站/信号信息 |
| `storage_list` | – | ✅ | 列手机目录（只允许 /sdcard 与家目录，防越狱） |
| `storage_read` | – | ✅ | 读手机上的文本文件 |
| `storage_write` | ✅ | ✅ | 往手机写文本文件（备忘录/AI 生成的说明直达手机） |
| `share_file` | ✅ | ✅ | 调起系统分享面板分享文件 |
| `open_url` | ✅ | ✅ | 在手机浏览器打开链接 |
| `confirm_dialog` | ✅ | ✅ | 在手机上弹确认框等人点（human-in-the-loop，AI 等你拍板再往下走） |
