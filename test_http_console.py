"""HTTP 传输 + console 网页，全走 mock/本地回环。"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "droid_mcp.py")
CONSOLE = os.path.join(HERE, "console.py")
HPORT, CPORT = 48441, 48442


def _post(url, obj):
    req = urllib.request.Request(
        url, data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode())


def _get(url):
    with urllib.request.urlopen(url, timeout=15) as r:
        return r.status, r.read().decode()


def _wait_http(url, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            _get(url)
            return True
        except OSError:
            time.sleep(0.3)
    return False


def test_http_transport_mock():
    p = subprocess.Popen(
        [sys.executable, SERVER, "--mock", "--http", "127.0.0.1:%d" % HPORT],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert _wait_http("http://127.0.0.1:%d/health" % HPORT)
        s, body = _get("http://127.0.0.1:%d/health" % HPORT)
        assert s == 200 and json.loads(body)["backend"] == "mock"
        s, r = _post("http://127.0.0.1:%d/mcp" % HPORT,
                     {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2025-06-18"}})
        assert s == 200 and r["result"]["serverInfo"]["name"] == "droid-mcp"
        s, r = _post("http://127.0.0.1:%d/mcp" % HPORT,
                     {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert s == 200 and len(r["result"]["tools"]) == 47
        s, r = _post("http://127.0.0.1:%d/mcp" % HPORT,
                     {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                      "params": {"name": "battery", "arguments": {}}})
        assert s == 200 and "82" in r["result"]["content"][0]["text"]
        # 通知回 202 且无 body 要求
        req = urllib.request.Request(
            "http://127.0.0.1:%d/mcp" % HPORT,
            data=json.dumps({"jsonrpc": "2.0",
                             "method": "notifications/initialized"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            assert r.status == 202
    finally:
        p.terminate()
        p.wait(timeout=5)


def test_console_pages_and_run():
    import tempfile
    logf = os.path.join(tempfile.gettempdir(), "dmc-test-log.jsonl")
    e = dict(os.environ, DROID_MCP_MOCK="1", DROID_MCP_LOG=logf)
    try:
        os.unlink(logf)
    except OSError:
        pass
    p = subprocess.Popen([sys.executable, CONSOLE, "--port", str(CPORT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=e)
    try:
        assert _wait_http("http://127.0.0.1:%d/api/status" % CPORT)
        s, body = _get("http://127.0.0.1:%d/" % CPORT)
        assert s == 200 and "droid-mcp console" in body
        s, body = _get("http://127.0.0.1:%d/api/status" % CPORT)
        st = json.loads(body)
        assert st["backend"] == "mock" and st["tools"] == 47
        s, body = _get("http://127.0.0.1:%d/api/tools" % CPORT)
        assert len(json.loads(body)["tools"]) == 47
        s, r = _post("http://127.0.0.1:%d/api/run" % CPORT,
                     {"name": "battery", "args": {}})
        assert s == 200 and "82" in r["content"][0]["text"]
        s, body = _get("http://127.0.0.1:%d/api/log" % CPORT)
        lines = json.loads(body)["lines"]
        assert any("battery" in ln for ln in lines), lines
    finally:
        p.terminate()
        p.wait(timeout=5)
