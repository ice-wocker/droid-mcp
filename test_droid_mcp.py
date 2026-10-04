"""droid-mcp v0.2 自检：协议 + 40 工具（mock）+ 只读 + 后端选择。"""
import json
import os
import subprocess
import sys

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "droid_mcp.py")
MUTATING = {"sms_send", "call_dial", "clipboard_set", "notify",
            "notification_remove", "toast", "vibrate", "torch",
            "brightness_set", "volume_set", "wallpaper_set", "media_scan",
            "media_play", "camera_photo", "mic_record", "tts_speak",
            "wifi_toggle", "storage_write", "share_file", "open_url",
            "confirm_dialog", "app_launch", "fingerprint_auth", "ir_blast"}


class Client:
    def __init__(self, *extra, env=None):
        e = dict(os.environ)
        if env:
            e.update(env)
        self.p = subprocess.Popen(
            [sys.executable, SERVER, *extra],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, env=e,
        )
        self._id = 0

    def call(self, method, params=None):
        self._id += 1
        req = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            req["params"] = params
        self.p.stdin.write(json.dumps(req) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def notify(self, method, params=None):
        req = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            req["params"] = params
        self.p.stdin.write(json.dumps(req) + "\n")
        self.p.stdin.flush()

    def close(self):
        try:
            self.p.stdin.close()
        except BrokenPipeError:
            pass
        self.p.terminate()
        self.p.wait(timeout=5)


def _names(client):
    return [t["name"] for t in client.call("tools/list")["result"]["tools"]]


def test_initialize_negotiation():
    c = Client("--mock")
    try:
        r = c.call("initialize", {"protocolVersion": "2025-06-18"})
        assert r["result"]["protocolVersion"] == "2025-06-18"
        assert r["result"]["serverInfo"] == {"name": "droid-mcp", "version": "0.3.0"}
        r2 = c.call("initialize", {"protocolVersion": "2099-01-01"})
        assert r2["result"]["protocolVersion"] == "2025-06-18"
    finally:
        c.close()


def test_ping_and_notifications():
    c = Client("--mock")
    try:
        assert c.call("ping")["result"] == {}
        c.notify("notifications/initialized")
        assert c.call("ping")["result"] == {}
        r = c.call("nope")
        assert r["error"]["code"] == -32601
    finally:
        c.close()


def test_tools_list_has_47():
    c = Client("--mock")
    try:
        tools = c.call("tools/list")["result"]["tools"]
        assert len(tools) == 47, [t["name"] for t in tools]
        mut = [t["name"] for t in tools
               if t["name"] in MUTATING]
        assert len(mut) == 24, mut
        for t in tools:
            assert t["inputSchema"]["type"] == "object"
            assert t["description"]
    finally:
        c.close()


def test_all_tools_callable_in_mock():
    """47 个工具在 mock 下全调一遍：有参给最小参，没 isError 才算过。"""
    args = {"sms_inbox": {"limit": 1}, "call_log": {"limit": 1},
            "sms_send": {"to": "13800138000", "body": "hi"},
            "call_dial": {"number": "13800138000"},
            "clipboard_set": {"text": "hi"}, "notify": {"content": "hi"},
            "notification_remove": {"id": "x"}, "toast": {"text": "hi"},
            "vibrate": {"ms": 50}, "torch": {"on": True},
            "brightness_set": {"value": 100}, "volume_set": {"stream": "music", "value": 3},
            "wallpaper_set": {"path": "/sdcard/a.jpg"}, "media_scan": {"paths": ["/sdcard/a.jpg"]},
            "media_play": {"path": "/sdcard/a.mp3"}, "sensor_read": {"sensors": "light", "count": 1},
            "storage_read": {"path": "/sdcard/notes.txt"},
            "storage_write": {"path": "/sdcard/m.txt", "text": "hi"},
            "share_file": {"path": "/sdcard/a.jpg"}, "open_url": {"url": "https://example.com"},
            "location": {"provider": "network"}, "mic_record": {"seconds": 2},
            "tts_speak": {"text": "hi"}, "confirm_dialog": {"title": "t"},
            "wifi_toggle": {"on": True}, "camera_photo": {},
            "app_launch": {"package": "com.example.mock"},
            "ir_blast": {"frequency": 38000, "pattern": "100,200"},
            "fingerprint_auth": {}}
    c = Client("--mock")
    try:
        bad = []
        for name in _names(c):
            r = c.call("tools/call", {"name": name, "arguments": args.get(name, {})})
            if r["result"].get("isError"):
                bad.append((name, r["result"]["content"][0]["text"][:80]))
        assert not bad, bad
    finally:
        c.close()


def test_sms_mock_limit_and_code():
    c = Client("--mock")
    try:
        r = c.call("tools/call", {"name": "sms_inbox", "arguments": {"limit": 1}})
        text = r["result"]["content"][0]["text"]
        assert "482916" in text and "10086" not in text
    finally:
        c.close()


def test_screenshot_mock_returns_image():
    c = Client("--mock")
    try:
        r = c.call("tools/call", {"name": "screenshot", "arguments": {}})
        kinds = [x["type"] for x in r["result"]["content"]]
        assert "image" in kinds
    finally:
        c.close()


def test_unknown_tool_is_error_not_crash():
    c = Client("--mock")
    try:
        r = c.call("tools/call", {"name": "nope", "arguments": {}})
        assert r["result"]["isError"] is True
        assert c.call("ping")["result"] == {}
    finally:
        c.close()


def test_read_only_hides_all_21_mutating():
    c = Client("--mock", "--read-only")
    try:
        names = set(_names(c))
        assert not (names & MUTATING), names & MUTATING
        assert len(names) == 23
        r = c.call("tools/call", {"name": "notify", "arguments": {"content": "hi"}})
        assert r["result"]["isError"] is True
    finally:
        c.close()


def test_missing_and_bad_args():
    c = Client("--mock")
    try:
        r = c.call("tools/call", {"name": "notify", "arguments": {}})
        assert r["result"]["isError"] is True
        r = c.call("tools/call", {"name": "sms_inbox", "arguments": {"limit": "abc"}})
        assert r["result"]["isError"] is True  # 不能崩，必须是正经报错
        r = c.call("tools/call", {"name": "volume_set",
                                  "arguments": {"stream": "boom", "value": 3}})
        assert r["result"]["isError"] is True
        r = c.call("tools/call", {"name": "open_url",
                                  "arguments": {"url": "ftp://x"}})
        assert r["result"]["isError"] is True
    finally:
        c.close()


def test_no_termux_api_gives_helpful_error():
    # PATH 掏空模拟“没装 termux-api 的机器”：启动期就给三选一指南，不进 main loop
    e = dict(os.environ, PATH="/nonexistent")
    p = subprocess.Popen([sys.executable, SERVER, "--backend", "termux"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, env=e)
    try:
        _, err = p.communicate(input="", timeout=15)
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == 2
    assert "三选一" in err and "--mock" in err


def test_companion_unreachable_gives_guide():
    c = Client("--backend", "companion", "--companion", "http://127.0.0.1:1",
               "--token", "x")
    try:
        # 启动时连不上 companion 应该直接退出（exit 2），stdout 关掉
        assert c.p.stdout.readline() == ""
    finally:
        c.close()


def test_companion_matrix_is_explicit():
    """防回归：companion 不支持集必须显式声明（曾出现过死键导致 17 个工具误标 ✅）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("dm", SERVER)
    dm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dm)
    no = {t["name"] for t in dm.TOOLS if not t.get("_companion", True)}
    assert no == {"audio_info", "brightness_set", "camera_info", "camera_photo",
                  "cell_info", "confirm_dialog", "fingerprint_auth", "ir_blast",
                  "media_info", "media_play", "media_scan", "mic_record",
                  "notification_list", "open_url", "screenshot", "sensor_list",
                  "sensor_read", "share_file", "torch", "tts_engines",
                  "tts_speak", "usb_list", "voice_transcribe", "volume_set",
                  "wallpaper_set", "wifi_scan", "wifi_toggle"}, no


def test_storage_jail_blocks_escape():
    import importlib.util
    spec = importlib.util.spec_from_file_location("dm", SERVER)
    dm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dm)
    for bad in ["/etc/passwd", "/sdcard/../etc/x", "/data/data/evil"]:
        try:
            dm._safe_path(bad)
        except dm.ToolError:
            continue
        raise AssertionError("越狱没拦住：" + bad)
