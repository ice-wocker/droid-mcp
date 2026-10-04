#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""droid-mcp — 你的安卓手机，变成 MCP 工具。

任意 MCP 客户端（Claude Code / Claude Desktop / OpenCode…）配上它，
AI 就能：读短信验证码、查通话记录/联系人、看电池、读写剪贴板、
发通知、截屏、定位、查 Wi-Fi——全程本机 Termux:API，不经过任何云。

零第三方依赖，只有 Python 标准库。单文件，读完即懂。

用法：
    python3 droid_mcp.py                 # stdio 模式（给 MCP 客户端调）
    python3 droid_mcp.py --mock          # 演示/CI 模式，不碰真机
    python3 droid_mcp.py --read-only     # 只读模式，隐藏写入类工具
    DROID_MCP_MOCK=1 / DROID_MCP_READ_ONLY=1 也认（环境变量方式）

协议：MCP over stdio（NDJSON 的 JSON-RPC 2.0）。
实现的方法：initialize / ping / tools/list / tools/call，
以及 notifications/*（收到不回）。
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile

VERSION = "0.1.0"
PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
MAX_TEXT = 12000
MAX_IMAGE_BYTES = 700_000

MOCK = "--mock" in sys.argv[1:] or os.environ.get("DROID_MCP_MOCK") == "1"
READ_ONLY = "--read-only" in sys.argv[1:] or os.environ.get("DROID_MCP_READ_ONLY") == "1"


def log(msg):
    print("[droid-mcp] " + str(msg), file=sys.stderr, flush=True)


class ToolError(Exception):
    """工具执行失败：会变成 isError 的 tool result，而不是整条连接炸掉。"""


# ---------------------------------------------------------------- 底层

def _exe(name):
    """找 termux-<name>，找不到就报“怎么装”，而不是 FileNotFoundError 吓人。"""
    exe = shutil.which("termux-" + name)
    if exe is None:
        raise ToolError(
            "termux-%s 不可用。需要：1) 安装 Termux:API App；"
            "2) 手机上 `pkg install termux-api`。\n"
            "没有真机时可以用 --mock 模式先玩起来。" % name
        )
    return exe


def _run_json(name, argv, timeout=10):
    """跑 termux-<name>，返回解析后的 JSON（多数 API 直接吐 JSON）。"""
    exe = _exe(name)
    try:
        p = subprocess.run([exe] + argv, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ToolError("termux-%s %ds 没响应：手机息屏/Termux:API 没授权都有可能，"
                        "亮屏后重试。" % (name, timeout))
    if p.returncode != 0:
        raise ToolError("termux-%s 失败：%s" % (name, (p.stderr or p.stdout).strip()[:300]))
    out = p.stdout.strip()
    if not out:
        raise ToolError("termux-%s 空输出：大概率 Termux:API 没授权，去手机上确认授权。" % name)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"_raw": out}


def _text(obj):
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2)
    if len(s) > MAX_TEXT:
        s = s[:MAX_TEXT] + "\n…[截断，共 %d 字符]" % len(s)
    return [{"type": "text", "text": s}]


def _mock_note():
    return "(mock 数据，非真机)"


# ---------------------------------------------------------------- mock 数据

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
                 "accuracy": 18.0, "mock": True},
    "wifi": {"ssid": "MockWiFi_5G", "bssid": "02:00:00:00:00:00",
             "rssi": -52, "link_speed_mbps": 866, "frequency": 5180},
}


# ---------------------------------------------------------------- 工具实现

def _t_device_info(a):
    return _MOCK["device_info"] if MOCK else _run_json("telephony-deviceinfo", [])


def _t_battery(a):
    return _MOCK["battery"] if MOCK else _run_json("battery-status", [])


def _t_sms_inbox(a):
    if MOCK:
        msgs = _MOCK["sms_inbox"][: max(1, min(int(a.get("limit", 10)), 50))]
        return {"messages": msgs, "_note": _mock_note()}
    argv = ["-l", str(max(1, min(int(a.get("limit", 10)), 100)))]
    if a.get("offset"):
        argv += ["-o", str(int(a["offset"]))]
    return _run_json("sms-list", argv, timeout=15)


def _t_call_log(a):
    if MOCK:
        return {"calls": _MOCK["call_log"], "_note": _mock_note()}
    argv = ["-l", str(max(1, min(int(a.get("limit", 20)), 100)))]
    return _run_json("call-log", argv, timeout=15)


def _t_contacts(a):
    if MOCK:
        return {"contacts": _MOCK["contacts"], "_note": _mock_note()}
    return _run_json("contact-list", [], timeout=15)


def _t_clipboard_get(a):
    if MOCK:
        return {"text": _MOCK["clipboard"], "_note": _mock_note()}
    exe = _exe("clipboard-get")
    try:
        p = subprocess.run([exe], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        raise ToolError("termux-clipboard-get 超时：先去手机上打开一次 Termux 授权。")
    if p.returncode != 0:
        raise ToolError("termux-clipboard-get 失败：" + (p.stderr or "").strip()[:200])
    return {"text": p.stdout}


def _t_clipboard_set(a):
    text = a.get("text", "")
    if not isinstance(text, str) or not text:
        raise ToolError("clipboard_set 需要 text 参数。")
    if MOCK:
        return {"ok": True, "length": len(text), "_note": _mock_note()}
    exe = _exe("clipboard-set")
    p = subprocess.run([exe, text], capture_output=True, text=True, timeout=10)
    if p.returncode != 0:
        raise ToolError("termux-clipboard-set 失败：" + (p.stderr or "").strip()[:200])
    return {"ok": True, "length": len(text)}


def _t_notify(a):
    content = a.get("content", "")
    if not isinstance(content, str) or not content:
        raise ToolError("notify 需要 content 参数。")
    if MOCK:
        return {"ok": True, "id": a.get("id", "droid-mcp"), "_note": _mock_note()}
    argv = ["-t", str(a.get("title", "droid-mcp")), "-c", content,
            "--id", str(a.get("id", "droid-mcp"))]
    exe = _exe("notification")
    p = subprocess.run([exe] + argv, capture_output=True, text=True, timeout=10)
    if p.returncode != 0:
        raise ToolError("termux-notification 失败：" + (p.stderr or "").strip()[:200])
    return {"ok": True, "id": argv[5]}


def _t_toast(a):
    text = a.get("text", "")
    if not isinstance(text, str) or not text:
        raise ToolError("toast 需要 text 参数。")
    if MOCK:
        return {"ok": True, "_note": _mock_note()}
    exe = _exe("toast")
    p = subprocess.run([exe, text], capture_output=True, text=True, timeout=10)
    if p.returncode != 0:
        raise ToolError("termux-toast 失败：" + (p.stderr or "").strip()[:200])
    return {"ok": True}


def _t_screenshot(a):
    if MOCK:
        # 1x1 红色 PNG，占位说明格式是对的
        tiny = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
        return [{"type": "image",
                 "data": tiny, "mimeType": "image/png"},
                {"type": "text", "text": _mock_note()}]
    exe = _exe("screenshot")
    path = a.get("path") or os.path.join(tempfile.gettempdir(), "droid-mcp-shot.png")
    p = subprocess.run([exe, path], capture_output=True, text=True, timeout=15)
    if p.returncode != 0 or not os.path.exists(path):
        raise ToolError("termux-screenshot 失败（部分旧版 Termux:API 没有这个命令）："
                        + (p.stderr or "").strip()[:200])
    size = os.path.getsize(path)
    if size <= MAX_IMAGE_BYTES:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return [{"type": "image", "data": data, "mimeType": "image/png"},
                {"type": "text", "text": "已截屏：%s（%d 字节，已内嵌）" % (path, size)}]
    return _text({"path": path, "bytes": size,
                  "note": "图太大没内嵌，AI 可以读这个路径（同一台手机上跑客户端时）"})


def _t_location(a):
    if MOCK:
        d = dict(_MOCK["location"])
        d["_note"] = _mock_note()
        return d
    exe = _exe("location")
    provider = str(a.get("provider", "network"))
    if provider not in ("gps", "network", "passive"):
        raise ToolError("provider 只能是 gps / network / passive。")
    # location 是持续输出的流：取第一行完整 JSON 就杀掉，不依赖 -r 参数各版本差异
    p = subprocess.Popen([exe, "-p", provider], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    try:
        line = ""
        import time
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


def _t_wifi_status(a):
    if MOCK:
        d = dict(_MOCK["wifi"])
        d["_note"] = _mock_note()
        return d
    return _run_json("wifi-connectioninfo", [])


# ---------------------------------------------------------------- 注册表

def _S(desc, required=(), props=None):
    schema = {"type": "object", "properties": props or {}}
    if required:
        schema["required"] = list(required)
    return {"description": desc, "inputSchema": schema}


TOOLS = [
    {"name": "device_info", "fn": _t_device_info, "mutating": False,
     **_S("手机基本信息（厂商/机型/安卓版本）。先调它确认连的是哪台手机。")},
    {"name": "battery", "fn": _t_battery, "mutating": False,
     **_S("电池：电量/充电状态/健康度/温度。")},
    {"name": "sms_inbox", "fn": _t_sms_inbox, "mutating": False,
     **_S("读短信收件箱。最常用的就是帮人找验证码。",
           props={"limit": {"type": "integer", "description": "条数，默认 10，最大 100"},
                  "offset": {"type": "integer", "description": "偏移"}})},
    {"name": "call_log", "fn": _t_call_log, "mutating": False,
     **_S("通话记录。",
           props={"limit": {"type": "integer", "description": "条数，默认 20，最大 100"}})},
    {"name": "contacts", "fn": _t_contacts, "mutating": False,
     **_S("通讯录（姓名+号码）。")},
    {"name": "clipboard_get", "fn": _t_clipboard_get, "mutating": False,
     **_S("读手机剪贴板。")},
    {"name": "clipboard_set", "fn": _t_clipboard_set, "mutating": True,
     **_S("写手机剪贴板。让 AI 把查到的验证码/链接直接塞进你手机剪贴板。",
           required=("text",), props={"text": {"type": "string"}})},
    {"name": "notify", "fn": _t_notify, "mutating": True,
     **_S("发一条系统通知。适合「跑完了叫我」这种场景。",
           required=("content",),
           props={"title": {"type": "string", "description": "标题，默认 droid-mcp"},
                  "content": {"type": "string"},
                  "id": {"type": "string", "description": "同 id 会覆盖上一条"}})},
    {"name": "toast", "fn": _t_toast, "mutating": True,
     **_S("屏幕底部弹个 Toast（一闪而过的小提示）。",
           required=("text",), props={"text": {"type": "string"}})},
    {"name": "screenshot", "fn": _t_screenshot, "mutating": False,
     **_S("截屏。图小直接内嵌回传，太大只给路径。",
           props={"path": {"type": "string", "description": "保存路径，默认临时目录"}})},
    {"name": "location", "fn": _t_location, "mutating": False,
     **_S("定位（经纬度+精度）。室内用 network，室外要精度用 gps（慢）。",
           props={"provider": {"type": "string",
                               "description": "gps / network / passive，默认 network"}})},
    {"name": "wifi_status", "fn": _t_wifi_status, "mutating": False,
     **_S("当前 Wi-Fi 连接信息（SSID/信号/速率）。")},
]

BY_NAME = {t["name"]: t for t in TOOLS}


def visible_tools():
    if READ_ONLY:
        return [t for t in TOOLS if not t["mutating"]]
    return TOOLS


# ---------------------------------------------------------------- JSON-RPC

def _ok(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_,
            "error": {"code": code, "message": message}}


def handle(req):
    """处理一条 JSON-RPC 消息。返回响应 dict，或 None（通知无需回）。"""
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
        try:
            out = tool["fn"](args)
        except ToolError as e:
            return _ok(id_, {"content": [{"type": "text", "text": str(e)}],
                             "isError": True})
        except Exception as e:  # 工具崩了也不能把整条连接带走
            log("tool %s crashed: %r" % (name, e))
            return _ok(id_, {"content": [{"type": "text", "text": "工具内部错误：%s" % e}],
                             "isError": True})
        if isinstance(out, list):  # screenshot 这类多段 content
            return _ok(id_, {"content": out})
        return _ok(id_, {"content": _text(out)})
    if method.startswith("notifications/"):
        return None
    if id_ is None:
        return None
    return _err(id_, -32601, "不支持的方法：%s" % method)


def main():
    log("droid-mcp %s 启动（mock=%s read_only=%s）" % (VERSION, MOCK, READ_ONLY))
    stdin = sys.stdin
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            resp = handle(req)
        except Exception as e:  # 最后一道防线
            log("handle crashed: %r" % e)
            resp = _err(req.get("id"), -32603, "内部错误")
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
