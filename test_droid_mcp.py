"""droid-mcp 自检：协议握手 + 工具调用，全走 --mock，不碰真机。"""
import json
import os
import subprocess
import sys

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "droid_mcp.py")


class Client:
    """起一个 server 子进程，一问一答。"""

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


def test_initialize_negotiation():
    c = Client("--mock")
    try:
        r = c.call("initialize", {"protocolVersion": "2025-06-18"})
        assert r["result"]["protocolVersion"] == "2025-06-18"
        assert r["result"]["serverInfo"]["name"] == "droid-mcp"
        # 客户端乱报版本，服务端给最新的，不掀桌
        r2 = c.call("initialize", {"protocolVersion": "2099-01-01"})
        assert r2["result"]["protocolVersion"] == "2025-06-18"
    finally:
        c.close()


def test_ping_and_notifications():
    c = Client("--mock")
    try:
        assert c.call("ping")["result"] == {}
        c.notify("notifications/initialized")  # 不回、不炸就行
        r = c.call("ping")
        assert r["result"] == {}
    finally:
        c.close()


def test_tools_list_has_12():
    c = Client("--mock")
    try:
        tools = c.call("tools/list")["result"]["tools"]
        names = [t["name"] for t in tools]
        assert len(tools) == 12, names
        for t in tools:
            assert t["inputSchema"]["type"] == "object"
        assert "sms_inbox" in names and "screenshot" in names
    finally:
        c.close()


def test_call_battery_mock():
    c = Client("--mock")
    try:
        r = c.call("tools/call", {"name": "battery", "arguments": {}})
        assert "isError" not in r["result"]
        text = r["result"]["content"][0]["text"]
        assert "82" in text  # mock 电量
    finally:
        c.close()


def test_call_sms_mock_limit():
    c = Client("--mock")
    try:
        r = c.call("tools/call", {"name": "sms_inbox", "arguments": {"limit": 1}})
        text = r["result"]["content"][0]["text"]
        assert "482916" in text  # mock 验证码在
        assert "10086" not in text  # limit=1 生效
    finally:
        c.close()


def test_screenshot_mock_returns_image():
    c = Client("--mock")
    try:
        r = c.call("tools/call", {"name": "screenshot", "arguments": {}})
        kinds = [c["type"] for c in r["result"]["content"]]
        assert "image" in kinds
        img = [c for c in r["result"]["content"] if c["type"] == "image"][0]
        assert img["mimeType"] == "image/png" and len(img["data"]) > 50
    finally:
        c.close()


def test_unknown_tool_is_error_not_crash():
    c = Client("--mock")
    try:
        r = c.call("tools/call", {"name": "nope", "arguments": {}})
        assert r["result"]["isError"] is True
        # 连接还活着
        assert c.call("ping")["result"] == {}
    finally:
        c.close()


def test_read_only_hides_and_blocks_writes():
    c = Client("--mock", "--read-only")
    try:
        names = [t["name"] for t in c.call("tools/list")["result"]["tools"]]
        assert "clipboard_set" not in names and "notify" not in names
        assert "battery" in names
        r = c.call("tools/call", {"name": "notify",
                                  "arguments": {"content": "hi"}})
        assert r["result"]["isError"] is True
    finally:
        c.close()


def test_missing_arg_is_error():
    c = Client("--mock")
    try:
        r = c.call("tools/call", {"name": "notify", "arguments": {}})
        assert r["result"]["isError"] is True
        assert "content" in r["result"]["content"][0]["text"]
    finally:
        c.close()


def test_no_termux_api_gives_helpful_error():
    # PATH 掏空模拟“没装 termux-api 的机器”，必须给人话而不是 traceback
    c = Client(env={"PATH": "/nonexistent", "DROID_MCP_MOCK": ""})
    try:
        r = c.call("tools/call", {"name": "battery", "arguments": {}})
        assert r["result"]["isError"] is True
        assert "Termux:API" in r["result"]["content"][0]["text"]
    finally:
        c.close()
