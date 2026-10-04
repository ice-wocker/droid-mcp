#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""droid-mcp v0.2 — 你的安卓手机，变成 MCP 工具。

任意 MCP 客户端（Claude Code / Claude Desktop / OpenCode…）配上它，
AI 就能用手机：40 个工具，短信/电话/剪贴板/通知/相机/传感器/文件……

三后端自动切换（--backend 指定，默认 auto）：
  termux     手机 Termux 里跑，调 termux-* 命令（功能最全，40/40）
  companion  连 companion APK（http://手机IP:4833），不用装 Termux（19/40，数据类全覆盖）
  mock       演示/CI，不碰真机（40/40 全是假数据）

零第三方依赖，只有 Python 标准库。单文件，读完即懂。

用法：
    python3 droid_mcp.py [--backend auto|termux|companion|mock]
                         [--companion http://192.168.1.5:4833] [--token xxx]
                         [--read-only] [--mock]
    DROID_MCP_BACKEND / DROID_MCP_COMPANION / DROID_MCP_TOKEN / DROID_MCP_MOCK=1 也认。
    python3 droid_mcp.py --dump-tools-md   # 生成文档用的工具表（docs/TOOLS.md）
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

VERSION = "0.3.0"
PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
MAX_TEXT = 12000
MAX_IMAGE_BYTES = 700_000
COMPANION_PORT = 4833

_argv = sys.argv[1:]
READ_ONLY = "--read-only" in _argv or os.environ.get("DROID_MCP_READ_ONLY") == "1"
_MOCK_FLAG = "--mock" in _argv or os.environ.get("DROID_MCP_MOCK") == "1"


def _opt(name, default=None):
    if name in _argv:
        i = _argv.index(name)
        if i + 1 < len(_argv) and not _argv[i + 1].startswith("--"):
            return _argv[i + 1]
    return os.environ.get("DROID_MCP_" + name.upper().lstrip("-").replace("-", "_"), default)


BACKEND_WANT = (_opt("--backend", "auto") or "auto").lower()
COMPANION_URL = (_opt("--companion") or "").rstrip("/")
COMPANION_TOKEN = _opt("--token") or ""


def log(msg):
    print("[droid-mcp] " + str(msg), file=sys.stderr, flush=True)


class ToolError(Exception):
    """工具执行失败：变成 isError 的 tool result，不掀桌。"""


def _num(a, key, default, lo, hi):
    try:
        v = int(a.get(key, default))
    except (TypeError, ValueError):
        raise ToolError("%s 得是数字。" % key)
    return max(lo, min(v, hi))


# ================================================================ 后端

class Backend:
    name = "base"

    def tx(self, cmd, argv, timeout=10):
        """跑 termux-<cmd>，返回解析后的 JSON。"""
        raise ToolError("当前后端不支持 termux 命令。")

    def tx_raw(self, argv0, timeout=10):
        """跑完整命令（含 termux- 前缀），返回原文。"""
        raise ToolError("当前后端不支持。")

    def hx(self, method, path, params=None, body=None, timeout=12):
        """调 companion HTTP API，返回 data（已拆 envelop）。"""
        raise ToolError("当前后端不支持 companion API。")


class TermuxBackend(Backend):
    name = "termux"

    @staticmethod
    def available():
        return shutil.which("termux-battery-status") is not None

    def _exe(self, cmd):
        exe = shutil.which("termux-" + cmd)
        if exe is None:
            raise ToolError(
                "termux-%s 不可用。需要：1) 安装 Termux:API App；"
                "2) `pkg install termux-api`。\n"
                "没装的话可以用 companion APK（--backend companion，见 docs/COMPANION.md）"
                "或 --mock 先玩起来。" % cmd)
        return exe

    def tx(self, cmd, argv, timeout=10):
        exe = self._exe(cmd)
        try:
            p = subprocess.run([exe] + argv, capture_output=True, text=True,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ToolError("termux-%s %ds 没响应：手机息屏/没授权都有可能，亮屏后重试。"
                            % (cmd, timeout))
        if p.returncode != 0:
            raise ToolError("termux-%s 失败：%s" % (cmd, (p.stderr or p.stdout).strip()[:300]))
        out = p.stdout.strip()
        if not out:
            raise ToolError("termux-%s 空输出：大概率没授权，去手机上确认授权。" % cmd)
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"_raw": out}

    def tx_raw(self, argv0, timeout=10):
        exe = self._exe(argv0[0].replace("termux-", "", 1) if argv0[0].startswith("termux-") else argv0[0])
        try:
            p = subprocess.run([exe] + argv0[1:], capture_output=True, text=True,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ToolError("%s 超时。" % argv0[0])
        if p.returncode != 0:
            raise ToolError("%s 失败：%s" % (argv0[0], (p.stderr or p.stdout).strip()[:300]))
        return p.stdout


class CompanionBackend(Backend):
    name = "companion"

    def __init__(self, base, token):
        self.base = base
        self.token = token
        try:
            pong = self.hx("GET", "/api/ping", timeout=8)
        except ToolError as e:
            raise ToolError("连不上 companion（%s）：确认 App 开着、同一 Wi-Fi、IP 对、token 对。"
                            % e)
        if not isinstance(pong, dict) or pong.get("name") != "droid-mcp-companion":
            raise ToolError("连上了但它不是 droid-mcp companion（防连错服务），IP 再核对下。")

    def hx(self, method, path, params=None, body=None, timeout=12):
        url = self.base + path
        q = dict(params or {})
        if self.token:
            q["token"] = self.token
        if q:
            url += "?" + urllib.parse.urlencode(q)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                env = json.loads(r.read().decode())
        except Exception as e:
            raise ToolError("companion 请求失败（%s %s）：%s" % (method, path, e))
        if not env.get("ok"):
            raise ToolError("companion 说不：%s" % env.get("error", "?"))
        return env.get("data")


class MockBackend(Backend):
    name = "mock"


_MOCK = {
    "device_info": {"manufacturer": "Google", "model": "Pixel_Mock",
                    "android_version": "15", "sdk": "35"},
    "battery": {"percentage": 82, "status": "DISCHARGING",
                "health": "GOOD", "temperature": 28.5},
    "sms_inbox": [
        {"number": "+86 138 0013 8000", "body": "【MockPay】验证码 482916，5 分钟内有效。",
         "date": "2026-10-04 10:00:00", "type": "inbox"},
        {"number": "10086", "body": "本月流量已用 8.2GB，剩余 1.8GB。",
         "date": "2026-10-03 09:12:00", "type": "inbox"},
    ],
    "call_log": [
        {"number": "+86 139 0013 9000", "name": "Mock 妈",
         "type": "incoming", "duration": 183, "date": "2026-10-03 20:01:00"},
    ],
    "contacts": [
        {"name": "Mock 妈", "number": "+86 139 0013 9000"},
        {"name": "Mock 快递", "number": "+86 137 0013 7000"},
    ],
    "clipboard": "mock 剪贴板内容",
    "location": {"provider": "network", "latitude": 31.2304, "longitude": 121.4737,
                 "accuracy": 18.0},
    "wifi": {"ssid": "MockWiFi_5G", "bssid": "02:00:00:00:00:00",
             "rssi": -52, "link_speed_mbps": 866},
    "wifi_scan": [{"ssid": "MockWiFi_5G", "bssid": "02:00:00:00:00:00", "rssi": -52},
                  {"ssid": "Neighbor_2.4G", "bssid": "02:00:00:00:00:01", "rssi": -71}],
    "sensors": [{"name": "accelerometer", "vendor": "Mock"},
                {"name": "gyroscope", "vendor": "Mock"},
                {"name": "light", "vendor": "Mock"}],
    "sensor_values": {"accelerometer": [0.1, 0.2, 9.8]},
    "audio": {"streams": ["alarm", "music", "notification", "ring", "system", "voicecall"]},
    "cameras": [{"id": "0", "facing": "back"}, {"id": "1", "facing": "front"}],
    "cell": {"type": "lte", "mcc": 460, "mnc": 0, "signal_dbm": -95},
    "notifications": [{"id": "mock1", "package": "com.example.mock", "title": "Mock 通知"}],
    "tts_engines": [{"name": "com.google.android.tts", "label": "Google TTS"}],
}


def _mock_note():
    return "(mock 数据，非真机)"


def _need_termux(name):
    raise ToolError("%s companion v1 不支持：切 --backend termux（见 README 兼容矩阵）。"
                    % name)


# ================================================================ 沙盒存储

def _safe_path(p):
    """只允许 /sdcard 与家目录。防 ../ 越狱（abspath 归一化后再比）。"""
    roots = [r for r in ("/sdcard", os.path.expanduser("~"),
                         "/storage/emulated/0") if os.path.isdir(r)]
    if not roots:
        raise ToolError("这台机器没有 /sdcard 也没有家目录，storage 工具用不了。")
    abs_ = os.path.abspath(os.path.expanduser(str(p or "/sdcard")))
    if not any(abs_ == r or abs_.startswith(r.rstrip("/") + "/") for r in roots):
        raise ToolError("路径越界：只允许 %s 里面。" % "、".join(roots))
    return abs_


# ================================================================ 工具实现

def _t_device_info(a, be):
    if isinstance(be, MockBackend):
        return _MOCK["device_info"]
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/device/info")
    return be.tx("telephony-deviceinfo", [])


def _t_battery(a, be):
    if isinstance(be, MockBackend):
        return _MOCK["battery"]
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/battery")
    return be.tx("battery-status", [])


def _t_sms_inbox(a, be):
    limit = _num(a, "limit", 10, 1, 100)
    offset = _num(a, "offset", 0, 0, 100000)
    if isinstance(be, MockBackend):
        return {"messages": _MOCK["sms_inbox"][:limit], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/sms/inbox", {"limit": limit, "offset": offset})
    argv = ["-l", str(limit)]
    if offset:
        argv += ["-o", str(offset)]
    return be.tx("sms-list", argv, timeout=15)


def _t_sms_send(a, be):
    to, body = a.get("to", ""), a.get("body", "")
    if not to or not body:
        raise ToolError("sms_send 需要 to 和 body。")
    if isinstance(be, MockBackend):
        return {"ok": True, "to": to, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("POST", "/api/sms/send", body={"to": to, "body": body})
    p = be.tx_raw(["termux-sms-send", "-n", str(to), str(body)], timeout=20)
    return {"ok": True, "output": p.strip()[:200]}


def _t_call_log(a, be):
    limit = _num(a, "limit", 20, 1, 100)
    if isinstance(be, MockBackend):
        return {"calls": _MOCK["call_log"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/call/log", {"limit": limit})
    return be.tx("call-log", ["-l", str(limit)], timeout=15)


def _t_call_dial(a, be):
    number = str(a.get("number", "")).strip()
    if not number:
        raise ToolError("call_dial 需要 number。这是真拨号，会产生话费，请确认。")
    if isinstance(be, MockBackend):
        return {"ok": True, "number": number, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("POST", "/api/call/dial", body={"number": number})
    be.tx_raw(["termux-telephony-call", number], timeout=10)
    return {"ok": True, "number": number}


def _t_contacts(a, be):
    if isinstance(be, MockBackend):
        return {"contacts": _MOCK["contacts"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/contacts")
    return be.tx("contact-list", [], timeout=15)


def _t_clipboard_get(a, be):
    if isinstance(be, MockBackend):
        return {"text": _MOCK["clipboard"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/clipboard/get")
    return {"text": be.tx_raw(["termux-clipboard-get"], timeout=10)}


def _t_clipboard_set(a, be):
    text = a.get("text", "")
    if not isinstance(text, str) or not text:
        raise ToolError("clipboard_set 需要 text 参数。")
    if isinstance(be, MockBackend):
        return {"ok": True, "length": len(text), "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("POST", "/api/clipboard/set", body={"text": text})
    be.tx_raw(["termux-clipboard-set", text], timeout=10)
    return {"ok": True, "length": len(text)}


def _t_notify(a, be):
    content = a.get("content", "")
    if not isinstance(content, str) or not content:
        raise ToolError("notify 需要 content 参数。")
    if isinstance(be, MockBackend):
        return {"ok": True, "id": a.get("id", "droid-mcp"), "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("POST", "/api/notify",
                     body={"title": a.get("title", "droid-mcp"),
                           "content": content, "id": a.get("id", "droid-mcp")})
    argv = ["-t", str(a.get("title", "droid-mcp")), "-c", content,
            "--id", str(a.get("id", "droid-mcp"))]
    be.tx_raw(["termux-notification", *argv], timeout=10)
    return {"ok": True, "id": argv[5]}


def _t_notification_remove(a, be):
    nid = str(a.get("id", "")).strip()
    if not nid:
        raise ToolError("notification_remove 需要 id（notify 时填的那个）。")
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("POST", "/api/notification/remove", body={"id": nid})
    be.tx_raw(["termux-notification-remove", nid], timeout=10)
    return {"ok": True}


def _t_notification_list(a, be):
    if isinstance(be, MockBackend):
        return {"notifications": _MOCK["notifications"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("notification_list")
    return be.tx("notification-list", [], timeout=10)


def _t_toast(a, be):
    text = a.get("text", "")
    if not isinstance(text, str) or not text:
        raise ToolError("toast 需要 text 参数。")
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("POST", "/api/toast", body={"text": text})
    be.tx_raw(["termux-toast", text], timeout=10)
    return {"ok": True}


def _t_vibrate(a, be):
    ms = _num(a, "ms", 200, 1, 10000)
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("POST", "/api/vibrate", body={"ms": ms})
    be.tx_raw(["termux-vibrate", "-d", str(ms)], timeout=10)
    return {"ok": True}


def _t_torch(a, be):
    on = bool(a.get("on", True))
    if isinstance(be, MockBackend):
        return {"ok": True, "on": on, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("torch")
    be.tx_raw(["termux-torch", "on" if on else "off"], timeout=10)
    return {"ok": True, "on": on}


def _t_brightness_set(a, be):
    v = _num(a, "value", 128, 1, 255)
    if isinstance(be, MockBackend):
        return {"ok": True, "value": v, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("brightness_set")
    be.tx_raw(["termux-brightness", str(v)], timeout=10)
    return {"ok": True, "value": v}


def _t_volume_set(a, be):
    stream = str(a.get("stream", "music"))
    if stream not in ("alarm", "music", "notification", "ring", "system", "voicecall", "dtmf"):
        raise ToolError("stream 只能是 alarm/music/notification/ring/system/voicecall/dtmf。")
    v = _num(a, "value", 5, 0, 15)
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("volume_set")
    be.tx_raw(["termux-volume", stream, str(v)], timeout=10)
    return {"ok": True, "stream": stream, "value": v}


def _t_wallpaper_set(a, be):
    path = str(a.get("path", "")).strip()
    if not path:
        raise ToolError("wallpaper_set 需要 path（手机上的图片路径）。")
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("wallpaper_set")
    argv = ["-f", path]
    if a.get("lockscreen"):
        argv.append("-l")
    be.tx_raw(["termux-wallpaper", *argv], timeout=15)
    return {"ok": True}


def _t_media_scan(a, be):
    paths = a.get("paths", [])
    if isinstance(paths, str):
        paths = [paths]
    if not paths:
        raise ToolError("media_scan 需要 paths（文件或目录数组），扫完图库才看得到新文件。")
    if isinstance(be, MockBackend):
        return {"ok": True, "scanned": len(paths), "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("media_scan")
    argv = (["-r"] if a.get("recursive") else []) + [str(p) for p in paths]
    be.tx_raw(["termux-media-scan", *argv], timeout=30)
    return {"ok": True, "scanned": len(paths)}


def _t_media_play(a, be):
    path = str(a.get("path", "")).strip()
    if not path:
        raise ToolError("media_play 需要 path（手机上的音频文件）。")
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("media_play")
    be.tx_raw(["termux-media-player", "play", path], timeout=10)
    return {"ok": True}


def _t_camera_photo(a, be):
    if isinstance(be, MockBackend):
        return {"path": "/sdcard/DCIM/mock.jpg", "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("camera_photo")
    path = str(a.get("path", "")).strip() or os.path.join(
        tempfile.gettempdir(), "droid-mcp-photo.jpg")
    argv = (["-c", str(int(a["camera"]))] if "camera" in a else []) + [path]
    be.tx_raw(["termux-camera-photo", *argv], timeout=20)
    return {"ok": True, "path": path}


def _t_mic_record(a, be):
    seconds = _num(a, "seconds", 10, 1, 120)
    if isinstance(be, MockBackend):
        return {"path": "/sdcard/Download/mock.m4a", "seconds": seconds,
                "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("mic_record")
    path = str(a.get("path", "")).strip() or os.path.join(
        tempfile.gettempdir(), "droid-mcp-rec.m4a")
    be.tx_raw(["termux-microphone-record", "-f", path, "-l", str(seconds)],
              timeout=seconds + 15)
    return {"ok": True, "path": path, "seconds": seconds}


def _t_tts_speak(a, be):
    text = a.get("text", "")
    if not isinstance(text, str) or not text:
        raise ToolError("tts_speak 需要 text 参数。")
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("tts_speak")
    argv = []
    if a.get("language"):
        argv += ["-l", str(a["language"])]
    if a.get("rate"):
        argv += ["-r", str(a["rate"])]
    argv.append(text)
    be.tx_raw(["termux-tts-speak", *argv], timeout=30)
    return {"ok": True}


def _t_tts_engines(a, be):
    if isinstance(be, MockBackend):
        return {"engines": _MOCK["tts_engines"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("tts_engines")
    return be.tx("tts-engines", [], timeout=10)


def _t_screenshot(a, be):
    if isinstance(be, MockBackend):
        tiny = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
        return [{"type": "image", "data": tiny, "mimeType": "image/png"},
                {"type": "text", "text": _mock_note()}]
    if isinstance(be, CompanionBackend):
        _need_termux("screenshot")
    exe = shutil.which("termux-screenshot")
    if exe is None:
        raise ToolError("termux-screenshot 不可用：部分旧版 Termux:API 没有这个命令，"
                        "升级 Termux:API App，或用 camera_photo 代替。")
    path = str(a.get("path", "")).strip() or os.path.join(
        tempfile.gettempdir(), "droid-mcp-shot.png")
    try:
        p = subprocess.run([exe, path], capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        raise ToolError("截屏超时。")
    if p.returncode != 0 or not os.path.exists(path):
        raise ToolError("截屏失败：" + (p.stderr or "").strip()[:200])
    size = os.path.getsize(path)
    if size <= MAX_IMAGE_BYTES:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return [{"type": "image", "data": data, "mimeType": "image/png"},
                {"type": "text", "text": "已截屏：%s（%d 字节，已内嵌）" % (path, size)}]
    return _text({"path": path, "bytes": size,
                  "note": "图太大没内嵌，AI 可以读这个路径（server 跑在手机上时）"})


def _t_location(a, be):
    if isinstance(be, MockBackend):
        d = dict(_MOCK["location"])
        d["_note"] = _mock_note()
        return d
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/location",
                     {"provider": str(a.get("provider", "network"))})
    provider = str(a.get("provider", "network"))
    if provider not in ("gps", "network", "passive"):
        raise ToolError("provider 只能是 gps / network / passive。")
    import time
    exe = TermuxBackend()._exe("location")
    p = subprocess.Popen([exe, "-p", provider], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    try:
        line = ""
        t0 = time.time()
        while time.time() - t0 < 12:
            chunk = p.stdout.readline() if p.stdout else ""
            if chunk.strip().startswith("{"):
                line = chunk
                break
            if p.poll() is not None:
                break
        if not line.strip():
            raise ToolError("12 秒没拿到定位：去室外/开 Wi-Fi 扫描后重试（gps 室内本就很慢）。")
        return json.loads(line)
    except json.JSONDecodeError:
        raise ToolError("定位输出解析失败。")
    finally:
        try:
            p.kill()
        except OSError:
            pass


def _t_wifi_status(a, be):
    if isinstance(be, MockBackend):
        d = dict(_MOCK["wifi"])
        d["_note"] = _mock_note()
        return d
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/wifi")
    return be.tx("wifi-connectioninfo", [])


def _t_wifi_scan(a, be):
    if isinstance(be, MockBackend):
        return {"networks": _MOCK["wifi_scan"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("wifi_scan")
    return be.tx("wifi-scaninfo", [], timeout=15)


def _t_wifi_toggle(a, be):
    on = bool(a.get("on", True))
    if isinstance(be, MockBackend):
        return {"ok": True, "on": on, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("wifi_toggle")
    be.tx_raw(["termux-wifi-enable", "true" if on else "false"], timeout=10)
    return {"ok": True, "on": on}


def _t_sensor_list(a, be):
    if isinstance(be, MockBackend):
        return {"sensors": _MOCK["sensors"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("sensor_list")
    return be.tx("sensor", ["-l"], timeout=10)


def _t_sensor_read(a, be):
    sensors = a.get("sensors", "accelerometer")
    if isinstance(sensors, list):
        sensors = ",".join(sensors)
    count = _num(a, "count", 3, 1, 50)
    if isinstance(be, MockBackend):
        return {"values": _MOCK["sensor_values"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("sensor_read")
    argv = ["-s", str(sensors), "-n", str(count)]
    if a.get("delay_ms"):
        argv += ["-d", str(_num(a, "delay_ms", 200, 20, 5000))]
    return be.tx("sensor", argv, timeout=count * 2 + 10)


def _t_audio_info(a, be):
    if isinstance(be, MockBackend):
        return {"audio": _MOCK["audio"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("audio_info")
    return be.tx("audio-info", [], timeout=10)


def _t_camera_info(a, be):
    if isinstance(be, MockBackend):
        return {"cameras": _MOCK["cameras"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("camera_info")
    return be.tx("camera-info", [], timeout=10)


def _t_cell_info(a, be):
    if isinstance(be, MockBackend):
        return {"cell": _MOCK["cell"], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("cell_info")
    return be.tx("telephony-cellinfo", [], timeout=10)


def _t_storage_list(a, be):
    path = str(a.get("path", "/sdcard"))
    if isinstance(be, MockBackend):
        return {"path": path,
                "entries": ["Download/", "DCIM/", "notes.txt"],
                "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/storage/list", {"path": path})
    abs_ = _safe_path(path)
    if not os.path.isdir(abs_):
        raise ToolError("不是目录：%s" % abs_)
    out = []
    for name in sorted(os.listdir(abs_))[:500]:
        full = os.path.join(abs_, name)
        out.append((name + "/") if os.path.isdir(full) else name)
    return {"path": abs_, "entries": out}


def _t_storage_read(a, be):
    path = str(a.get("path", "")).strip()
    if not path:
        raise ToolError("storage_read 需要 path。")
    max_bytes = _num(a, "max_bytes", 65536, 1, 1048576)
    if isinstance(be, MockBackend):
        return {"path": path, "text": "mock 文件内容\n第二行\n",
                "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/storage/read",
                     {"path": path, "max_bytes": max_bytes})
    abs_ = _safe_path(path)
    if not os.path.isfile(abs_):
        raise ToolError("不是文件：%s" % abs_)
    with open(abs_, "rb") as f:
        raw = f.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raw = raw[:max_bytes] + "\n…[截断]".encode("utf-8", errors="replace")
    try:
        return {"path": abs_, "text": raw.decode("utf-8", errors="replace")}
    except OSError as e:
        raise ToolError("读失败：%s" % e)


def _t_storage_write(a, be):
    path = str(a.get("path", "")).strip()
    text = a.get("text", "")
    if not path or not isinstance(text, str):
        raise ToolError("storage_write 需要 path 和 text。AI 生成的备忘录/图片说明直接存进手机。")
    if isinstance(be, MockBackend):
        return {"ok": True, "path": path, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("POST", "/api/storage/write",
                     body={"path": path, "text": text,
                           "overwrite": bool(a.get("overwrite", False))})
    abs_ = _safe_path(path)
    if os.path.exists(abs_) and not a.get("overwrite"):
        raise ToolError("文件已存在，不覆盖（加 overwrite=true 硬写）。")
    os.makedirs(os.path.dirname(abs_) or ".", exist_ok=True)
    with open(abs_, "w", encoding="utf-8") as f:
        f.write(text)
    return {"ok": True, "path": abs_, "bytes": len(text.encode())}


def _t_share_file(a, be):
    path = str(a.get("path", "")).strip()
    if not path:
        raise ToolError("share_file 需要 path（手机上的文件，调起系统分享面板）。")
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("share_file")
    be.tx_raw(["termux-share", path], timeout=10)
    return {"ok": True}


def _t_open_url(a, be):
    url = str(a.get("url", "")).strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ToolError("open_url 只接受 http(s) 链接。")
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("open_url")
    be.tx_raw(["termux-open-url", url], timeout=10)
    return {"ok": True}


def _t_confirm_dialog(a, be):
    title = str(a.get("title", "请确认"))
    if isinstance(be, MockBackend):
        return {"code": 0, "text": "yes (mock)", "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("confirm_dialog")
    argv = ["confirm", "-t", title]
    if a.get("hint"):
        argv += ["-i", str(a["hint"])]
    out = be.tx("dialog", argv, timeout=120)
    # termux-dialog confirm 回 {"code":0/-1,"text":"yes/no"}，原样透出
    return out if isinstance(out, dict) else {"_raw": out}


def _t_app_launch(a, be):
    package = str(a.get("package", "")).strip()
    if not package or "/" in package or " " in package:
        raise ToolError("app_launch 需要 package（应用包名，如 com.example.app）。")
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("POST", "/api/apps/launch", body={"package": package})
    activity = str(a.get("activity", "")).strip()
    if not activity:
        raise ToolError("Termux 下启动应用需要 activity（包名/启动页，如 .MainActivity）；"
                        "只给包名就能开的是 companion 后端（它认得 launcher）。")
    be.tx_raw(["termux-am", "start", "-n", package + "/" + activity], timeout=15)
    return {"ok": True}


def _t_app_list(a, be):
    if isinstance(be, MockBackend):
        return {"apps": [{"package": "com.example.mock", "label": "Mock 应用"}],
                "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        return be.hx("GET", "/api/apps")
    raise ToolError("app_list companion 独占：Termux 下列应用要 root，用 companion 后端。")


def _t_fingerprint_auth(a, be):
    if isinstance(be, MockBackend):
        return {"auth_result": "AUTH_RESULT_SUCCESS", "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("fingerprint_auth")
    argv = ["-t", str(a.get("title", "droid-mcp 请求确认"))]
    if a.get("description"):
        argv += ["-d", str(a["description"])]
    out = be.tx("fingerprint", argv, timeout=120)
    return out if isinstance(out, dict) else {"_raw": out}


def _t_voice_transcribe(a, be):
    if isinstance(be, MockBackend):
        return {"text": "mock 语音转写：明天下午三点开会", "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("voice_transcribe")
    # 无参数：直接听， partial 结果流里取第一段完整文本（走 Google 语音服务，要联网）
    out = be.tx("speech-to-text", [], timeout=40)
    return out if isinstance(out, dict) else {"text": out}


def _t_ir_blast(a, be):
    try:
        freq = int(a.get("frequency", 38000))
    except (TypeError, ValueError):
        raise ToolError("frequency 得是数字（常见 36000/38000/40000）。")
    pattern = str(a.get("pattern", "")).strip()
    if not pattern:
        raise ToolError("ir_blast 需要 pattern（红外码，逗号分隔的整数序列）与 frequency。")
    if isinstance(be, MockBackend):
        return {"ok": True, "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("ir_blast")
    be.tx_raw(["termux-infrared-transmit", "-f", str(freq), pattern], timeout=10)
    return {"ok": True}


def _t_usb_list(a, be):
    if isinstance(be, MockBackend):
        return {"devices": [], "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("usb_list")
    return be.tx("usb", ["-l"], timeout=10)


def _t_media_info(a, be):
    if isinstance(be, MockBackend):
        return {"state": "stopped", "_note": _mock_note()}
    if isinstance(be, CompanionBackend):
        _need_termux("media_info")
    return be.tx("media-player", ["info"], timeout=10)


# ================================================================ 注册表

def _S(desc, required=(), props=None, companion=True):
    """companion=False 的工具在 companion 后端会诚实报错（切 termux）。"""
    schema = {"type": "object", "properties": props or {}}
    if required:
        schema["required"] = list(required)
    return {"description": desc, "inputSchema": schema,
            "mutating": False, "_companion": companion}


def _M(desc, required=(), props=None, companion=True):
    d = _S(desc, required, props, companion)
    d["mutating"] = True
    return d


_I = {"type": "integer"}
_ST = {"type": "string"}

TOOLS = [
    {"name": "device_info", "fn": _t_device_info,
     **_S("手机基本信息（厂商/机型/安卓版本）。先调它确认连的是哪台手机。")},
    {"name": "battery", "fn": _t_battery,
     **_S("电池：电量/充电状态/健康度/温度。")},
    {"name": "sms_inbox", "fn": _t_sms_inbox,
     **_S("读短信收件箱。找验证码的主力。",
           props={"limit": {**_I, "description": "条数，默认 10，最大 100"},
                  "offset": {**_I, "description": "偏移"}})},
    {"name": "sms_send", "fn": _t_sms_send,
     **_M("发短信。真金白银的操作，客户端会先问你（companion App 内默认关闭，需手动开）。",
           required=("to", "body"),
           props={"to": {**_ST, "description": "号码，多个逗号分隔"},
                  "body": _ST})},
    {"name": "call_log", "fn": _t_call_log,
     **_S("通话记录。",
           props={"limit": {**_I, "description": "条数，默认 20，最大 100"}})},
    {"name": "call_dial", "fn": _t_call_dial,
     **_M("直接拨号（无确认框，会产生话费）。",
           required=("number",), props={"number": _ST})},
    {"name": "contacts", "fn": _t_contacts,
     **_S("通讯录（姓名+号码）。")},
    {"name": "clipboard_get", "fn": _t_clipboard_get,
     **_S("读手机剪贴板。")},
    {"name": "clipboard_set", "fn": _t_clipboard_set,
     **_M("写手机剪贴板。验证码/链接直达剪贴板。",
           required=("text",), props={"text": _ST})},
    {"name": "notify", "fn": _t_notify,
     **_M("发系统通知。「跑完了叫我」就靠它。",
           required=("content",),
           props={"title": {**_ST, "description": "默认 droid-mcp"},
                  "content": _ST, "id": {**_ST, "description": "同 id 覆盖上一条"}})},
    {"name": "notification_remove", "fn": _t_notification_remove,
     **_M("撤掉指定 id 的通知。",
           required=("id",), props={"id": _ST})},
    {"name": "notification_list", "fn": _t_notification_list,
     **_S("当前通知栏里都有啥。", companion=False)},
    {"name": "toast", "fn": _t_toast,
     **_M("底部 Toast（一闪而过的小提示）。",
           required=("text",), props={"text": _ST})},
    {"name": "vibrate", "fn": _t_vibrate,
     **_M("震动。",
           props={"ms": {**_I, "description": "毫秒，默认 200，最大 10000"}})},
    {"name": "torch", "fn": _t_torch,
     **_M("手电筒开关。",
           props={"on": {"type": "boolean", "description": "默认 true"}},
           companion=False)},
    {"name": "brightness_set", "fn": _t_brightness_set,
     **_M("屏幕亮度 1-255。",
           props={"value": {**_I, "description": "默认 128"}},
           companion=False)},
    {"name": "volume_set", "fn": _t_volume_set,
     **_M("调音量。",
           props={"stream": {**_ST, "description": "alarm/music/notification/ring/system/voicecall/dtmf"},
                  "value": {**_I, "description": "0-15"}},
           companion=False)},
    {"name": "wallpaper_set", "fn": _t_wallpaper_set,
     **_M("换壁纸（手机上的图片路径）。",
           required=("path",),
           props={"path": _ST, "lockscreen": {"type": "boolean", "description": "同时设锁屏"}},
           companion=False)},
    {"name": "media_scan", "fn": _t_media_scan,
     **_M("通知系统扫描文件（新照片/录音不出现在图库时用它）。",
           required=("paths",),
           props={"paths": {"type": "array", "items": _ST},
                  "recursive": {"type": "boolean"}},
           companion=False)},
    {"name": "media_play", "fn": _t_media_play,
     **_M("放一个音频文件。",
           required=("path",), props={"path": _ST},
           companion=False)},
    {"name": "camera_photo", "fn": _t_camera_photo,
     **_M("拍一张照片存手机上（回路径，不回图，省 token）。",
           props={"path": {**_ST, "description": "默认临时目录"},
                  "camera": {**_I, "description": "摄像头 id，见 camera_info"}},
           companion=False)},
    {"name": "mic_record", "fn": _t_mic_record,
     **_M("录音（回文件路径）。",
           props={"seconds": {**_I, "description": "默认 10，最长 120"},
                  "path": {**_ST, "description": "默认临时目录"}},
           companion=False)},
    {"name": "tts_speak", "fn": _t_tts_speak,
     **_M("手机开口说话（TTS）。",
           required=("text",),
           props={"text": _ST, "language": {**_ST, "description": "如 eng-USA"},
                  "rate": {"type": "number"}},
           companion=False)},
    {"name": "tts_engines", "fn": _t_tts_engines,
     **_S("可用的 TTS 引擎列表。", companion=False)},
    {"name": "screenshot", "fn": _t_screenshot,
     **_S("截屏。小图内嵌回传，大图只给路径。",
           props={"path": {**_ST, "description": "默认临时目录"}},
           companion=False)},
    {"name": "location", "fn": _t_location,
     **_S("定位。室内用 network，室外要精度用 gps（慢）。",
           props={"provider": {**_ST, "description": "gps/network/passive，默认 network"}})},
    {"name": "wifi_status", "fn": _t_wifi_status,
     **_S("当前 Wi-Fi（SSID/信号/速率）。")},
    {"name": "wifi_scan", "fn": _t_wifi_scan,
     **_S("扫描周围 Wi-Fi（要开定位开关，安卓规定的）。", companion=False)},
    {"name": "wifi_toggle", "fn": _t_wifi_toggle,
     **_M("Wi-Fi 开关。",
           props={"on": {"type": "boolean", "description": "默认 true"}},
           companion=False)},
    {"name": "sensor_list", "fn": _t_sensor_list,
     **_S("手机有哪些传感器。", companion=False)},
    {"name": "sensor_read", "fn": _t_sensor_read,
     **_S("读传感器（加速度/陀螺仪/光线…，做手机机器人必备）。",
           props={"sensors": {**_ST, "description": "逗号分隔，默认 accelerometer"},
                  "count": {**_I, "description": "读几次，默认 3，最大 50"},
                  "delay_ms": _I},
           companion=False)},
    {"name": "audio_info", "fn": _t_audio_info,
     **_S("音频系统信息（有哪些输出流）。", companion=False)},
    {"name": "camera_info", "fn": _t_camera_info,
     **_S("摄像头列表（camera_photo 的 id 从这来）。", companion=False)},
    {"name": "cell_info", "fn": _t_cell_info,
     **_S("基站/信号信息。", companion=False)},
    {"name": "storage_list", "fn": _t_storage_list,
     **_S("列手机目录（只允许 /sdcard 与家目录，防越狱）。",
           props={"path": {**_ST, "description": "默认 /sdcard"}})},
    {"name": "storage_read", "fn": _t_storage_read,
     **_S("读手机上的文本文件。",
           required=("path",),
           props={"path": _ST, "max_bytes": {**_I, "description": "默认 64KB"}})},
    {"name": "storage_write", "fn": _t_storage_write,
     **_M("往手机写文本文件（备忘录/AI 生成的说明直达手机）。已存在默认不覆盖。",
           required=("path", "text"),
           props={"path": _ST, "text": _ST,
                  "overwrite": {"type": "boolean"}})},
    {"name": "share_file", "fn": _t_share_file,
     **_M("调起系统分享面板分享文件。",
           required=("path",), props={"path": _ST},
           companion=False)},
    {"name": "open_url", "fn": _t_open_url,
     **_M("在手机浏览器打开链接。",
           required=("url",), props={"url": _ST},
           companion=False)},
    {"name": "confirm_dialog", "fn": _t_confirm_dialog,
     **_M("在手机上弹确认框等人点（human-in-the-loop，AI 等你拍板再往下走）。"
           "注意：会阻塞到超时（120s），超时算失败。",
           props={"title": {**_ST, "description": "默认 请确认"},
                  "hint": _ST},
           companion=False)},
    {"name": "app_launch", "fn": _t_app_launch,
     **_M("启动手机上的 App。companion 给包名就行；Termux 下要再给 activity。",
           required=("package",),
           props={"package": {**_ST, "description": "如 com.example.app"},
                  "activity": {**_ST, "description": "Termux 独占，如 .MainActivity"}})},
    {"name": "app_list", "fn": _t_app_list,
     **_S("已安装应用列表（包名+名称）。companion 独占，Termux 下要 root 才行。")},
    {"name": "fingerprint_auth", "fn": _t_fingerprint_auth,
     **_M("指纹/面容确认：最高级别的人工确认，比确认框更正式（解锁、转账类场景）。"
           "会阻塞等你按指纹，超时算失败。",
           props={"title": _ST, "description": _ST},
           companion=False)},
    {"name": "voice_transcribe", "fn": _t_voice_transcribe,
     **_S("听一段语音转文字（走系统语音服务，要联网）。开会录音转纪要就靠它。",
           companion=False)},
    {"name": "ir_blast", "fn": _t_ir_blast,
     **_M("红外发射（有红外头的手机当万能遥控器）。",
           required=("frequency", "pattern"),
           props={"frequency": {**_I, "description": "载波，常见 38000"},
                  "pattern": {**_ST, "description": "逗号分隔的整数序列"}},
           companion=False)},
    {"name": "usb_list", "fn": _t_usb_list,
     **_S("USB 口上插了啥（OTG 设备盘点）。", companion=False)},
    {"name": "media_info", "fn": _t_media_info,
     **_S("当前播放状态（谁在放歌）。", companion=False)},
]

BY_NAME = {t["name"]: t for t in TOOLS}
assert len(BY_NAME) == len(TOOLS), "工具名重复了"


def visible_tools():
    if READ_ONLY:
        return [t for t in TOOLS if not t["mutating"]]
    return TOOLS


# ================================================================ 后端选择

def select_backend(want=None, companion_url=None, token=None):
    """选后端。参数不给就读 CLI/env（给 console.py 留后门传参）。"""
    want = (want or BACKEND_WANT or "auto").lower()
    companion_url = companion_url if companion_url is not None else COMPANION_URL
    token = token if token is not None else COMPANION_TOKEN
    if _MOCK_FLAG or want == "mock":
        return MockBackend()
    if want == "companion" or (want == "auto" and companion_url):
        if not companion_url:
            raise ToolError("companion 后端需要 --companion http://手机IP:4833（+ --token）。")
        return CompanionBackend(companion_url, token)
    if want == "termux" or want == "auto":
        if TermuxBackend.available():
            return TermuxBackend()
        raise ToolError(
            "没找到 termux-* 命令。三选一：\n"
            "1) 手机 Termux 里跑（功能最全）：pkg install termux-api\n"
            "2) companion APK（不用 Termux）：--backend companion --companion http://手机IP:4833 --token xxx\n"
            "3) 先玩起来：--mock")
    raise ToolError("--backend 只能是 auto/termux/companion/mock。")


def _log_path():
    p = os.environ.get("DROID_MCP_LOG", os.path.join(
        os.path.expanduser("~"), ".droid-mcp", "calls.jsonl"))
    if p.lower() == "off":
        return None
    return p


def log_call(tool, ok, ms):
    """调用审计日志：给 console.py 看。只记工具名+成败+耗时，不记参数（短信内容不落盘）。"""
    path = _log_path()
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            import time
            f.write(json.dumps({"ts": time.strftime("%H:%M:%S"), "tool": tool,
                                "ok": ok, "ms": ms}, ensure_ascii=False) + "\n")
        if os.path.getsize(path) > 200 * 1024:  # 200KB 就只留后 500 行
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()[-500:]
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
    except OSError:
        pass


# ================================================================ JSON-RPC

def _ok(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_,
            "error": {"code": code, "message": message}}


def handle(req, be):
    if not isinstance(req, dict) or req.get("jsonrpc") != "2.0":
        return _err(None, -32600, "只要 JSON-RPC 2.0")
    method = req.get("method", "")
    id_ = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        want = params.get("protocolVersion", "")
        ver = want if want in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[-1]
        return _ok(id_, {"protocolVersion": ver,
                         "capabilities": {"tools": {}},
                         "serverInfo": {"name": "droid-mcp", "version": VERSION}})
    if method == "ping":
        return _ok(id_, {})
    if method == "tools/list":
        defs = [{"name": t["name"], "description": t["description"],
                 "inputSchema": t["inputSchema"]} for t in visible_tools()]
        return _ok(id_, {"tools": defs})
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        tool = BY_NAME.get(name)
        if tool is None or (READ_ONLY and tool["mutating"]):
            return _ok(id_, {"content": [{"type": "text",
                                          "text": "未知工具或只读模式下不可用：%s" % name}],
                             "isError": True})
        if not isinstance(args, dict):
            return _ok(id_, {"content": [{"type": "text", "text": "arguments 必须是对象"}],
                             "isError": True})
        for req_key in tool["inputSchema"].get("required", []):
            if req_key not in args:
                return _ok(id_, {"content": [{"type": "text",
                                              "text": "缺少参数：%s" % req_key}],
                                 "isError": True})
        # companion v1 不支持的工具：诚实报错，不硬调
        if isinstance(be, CompanionBackend) and not tool.get("_companion", True):
            return _ok(id_, {"content": [{"type": "text",
                                          "text": "%s companion v1 不支持：切 --backend termux "
                                                  "（见 README 兼容矩阵）或等后续版本。" % name}],
                             "isError": True})
        try:
            out = tool["fn"](args, be)
        except ToolError as e:
            return _ok(id_, {"content": [{"type": "text", "text": str(e)}],
                             "isError": True})
        except Exception as e:
            log("tool %s crashed: %r" % (name, e))
            return _ok(id_, {"content": [{"type": "text", "text": "工具内部错误：%s" % e}],
                             "isError": True})
        if isinstance(out, list):
            return _ok(id_, {"content": out})
        return _ok(id_, {"content": _text(out)})
    if method.startswith("notifications/"):
        return None
    if id_ is None:
        return None
    return _err(id_, -32601, "不支持的方法：%s" % method)


def _text(obj):
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2)
    if len(s) > MAX_TEXT:
        s = s[:MAX_TEXT] + "\n…[截断，共 %d 字符]" % len(s)
    return [{"type": "text", "text": s}]


def dump_tools_md():
    mut = sum(1 for t in TOOLS if t["mutating"])
    print("# droid-mcp 工具表（v%s，由 --dump-tools-md 生成）\n" % VERSION)
    print("共 %d 个工具（读 %d / 写 %d）。companion 列是 companion APK v1 是否支持。"
          % (len(TOOLS), len(TOOLS) - mut, mut))
    print("\n| 工具 | 写 | companion | 说明 |")
    print("|---|---|---|---|")
    for t in TOOLS:
        print("| `%s` | %s | %s | %s |" % (
            t["name"], "✅" if t["mutating"] else "–",
            "✅" if t.get("_companion", True) else "❌",
            t["description"].split("。")[0]))


def main():
    if "--dump-tools-md" in _argv:
        return dump_tools_md()
    http_at = _opt("--http")
    try:
        be = select_backend()
    except ToolError as e:
        sys.stderr.write("droid-mcp 启动失败：%s\n" % e)
        sys.exit(2)
    if http_at:
        return serve_http(http_at, be)
    log("droid-mcp %s 启动（backend=%s read_only=%s）" % (VERSION, be.name, READ_ONLY))
    import time
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        t0 = time.time()
        try:
            resp = handle(req, be)
        except Exception as e:
            log("handle crashed: %r" % e)
            resp = _err(req.get("id"), -32603, "内部错误")
        if isinstance(req, dict) and req.get("method") == "tools/call":
            ok = not ((resp or {}).get("result") or {}).get("isError", False)
            log_call(str((req.get("params") or {}).get("name", "?")), ok,
                     int((time.time() - t0) * 1000))
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def serve_http(at, be):
    """MCP over HTTP（Streamable HTTP 极简版）：POST /mcp 跑 JSON-RPC，
    通知回 202，GET /health 给探针。手机在兜里、agent 在云端时就靠它。"""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    host, port = at.rsplit(":", 1) if ":" in at else ("0.0.0.0", at or "4844")
    try:
        port = int(port)
    except ValueError:
        sys.stderr.write("--http 格式：host:port（如 0.0.0.0:4844）\n")
        sys.exit(2)

    import time as _t

    class H(BaseHTTPRequestHandler):
        server_version = "droid-mcp/" + VERSION

        def log_message(self, *a):
            pass

        def _send(self, code, obj, ctype="application/json"):
            body = b"" if obj is None else json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"ok": True, "name": "droid-mcp",
                                        "version": VERSION, "backend": be.name})
            return self._send(404, {"ok": False, "error": "只要 /mcp 与 /health"})

        def do_POST(self):
            if self.path != "/mcp":
                return self._send(404, {"ok": False, "error": "只要 /mcp 与 /health"})
            try:
                n = int(self.headers.get("Content-Length", 0))
            except ValueError:
                return self._send(400, {"jsonrpc": "2.0", "id": None,
                                        "error": {"code": -32700, "message": "坏请求"}})
            try:
                req = json.loads(self.rfile.read(n).decode() or "{}")
            except json.JSONDecodeError:
                return self._send(400, {"jsonrpc": "2.0", "id": None,
                                        "error": {"code": -32700, "message": "JSON 解析失败"}})
            t0 = _t.time()
            try:
                resp = handle(req, be)
            except Exception as e:
                log("handle crashed: %r" % e)
                resp = _err(req.get("id"), -32603, "内部错误")
            if isinstance(req, dict) and req.get("method") == "tools/call":
                ok = not ((resp or {}).get("result") or {}).get("isError", False)
                log_call(str((req.get("params") or {}).get("name", "?")), ok,
                         int((_t.time() - t0) * 1000))
            if resp is None:
                return self._send(202, None)
            return self._send(200, resp)

    log("droid-mcp %s HTTP 模式（backend=%s）：http://%s:%d/mcp" % (VERSION, be.name, host, port))
    ThreadingHTTPServer((host, port), H).serve_forever()


if __name__ == "__main__":
    main()
