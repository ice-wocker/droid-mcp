#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""droid-mcp console —— 手机管家网页版（标准库，无依赖）。

浏览器打开看：连的是真机还是 mock、47 个工具、最近调用日志，
还能直接在线试跑工具（走同一套后端与审批语义）。

用法：
    python3 console.py [--port 4855] [--backend ...] [--companion URL] [--token X] [--mock] [--read-only]
    # 后端参数与 droid_mcp.py 完全一致（同一份 argv 解析）
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import droid_mcp as dm

PORT = 4855
for _i, _a in enumerate(sys.argv[1:]):
    if _a == "--port" and _i + 2 <= len(sys.argv[1:]):
        try:
            PORT = int(sys.argv[1:][_i + 1])
        except ValueError:
            pass

BE = dm.select_backend()

PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>droid-mcp console</title>
<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2em auto;padding:0 1em;color:#222}
.card{border:1px solid #ddd;border-radius:8px;padding:1em;margin:1em 0}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:.3em .5em;font-size:.9em}
code{background:#f4f4f4;padding:.1em .3em;border-radius:3px}.mut{color:#c00}
#log{white-space:pre-wrap;background:#111;color:#0f0;padding:1em;border-radius:8px;max-height:300px;overflow:auto}
button{padding:.4em 1em;margin-top:.5em}textarea{width:100%;height:60px}</style>
</head><body>
<h1>📱 droid-mcp console <small id="ver"></small></h1>
<div class="card" id="status">加载中…</div>
<div class="card"><h3>在线试跑</h3>
<select id="tool"></select><br>
<textarea id="args" placeholder='参数 JSON，如 {"limit": 3}'>{}</textarea><br>
<button onclick="run()">执行</button>
<pre id="out"></pre></div>
<div class="card"><h3>调用日志（最近 100 条，不记参数内容）</h3><div id="log"></div></div>
<div class="card"><h3>工具表（<span id="n"></span> 个）</h3><table id="tools"></table></div>
<script>
async function j(u,o){const r=await fetch(u,o);return r.json()}
async function load(){
 const s=await j('/api/status');
 document.getElementById('ver').textContent='v'+s.version;
 document.getElementById('status').innerHTML=
  `后端：<code>${s.backend}</code> ｜ 只读：<code>${s.read_only}</code> ｜ 工具：<code>${s.tools} 个（写 ${s.mutating}）</code>`;
 const t=await j('/api/tools');
 document.getElementById('n').textContent=t.tools.length;
 document.getElementById('tools').innerHTML='<tr><th>工具</th><th>写</th><th>说明</th></tr>'+
  t.tools.map(x=>`<tr><td><code>${x.name}</code></td><td class="${x.mutating?'mut':''}">${x.mutating?'✏️':'–'}</td><td>${x.description}</td></tr>`).join('');
 document.getElementById('tool').innerHTML=t.tools.map(x=>`<option>${x.name}</option>`).join('');
 const l=await j('/api/log');
 document.getElementById('log').textContent=l.lines.join('\\n')||'(空)';
}
async function run(){
 const name=document.getElementById('tool').value;
 let args={}; try{args=JSON.parse(document.getElementById('args').value||'{}')}catch(e){alert('JSON 写错了');return}
 document.getElementById('out').textContent='跑中…';
 const r=await j('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,args})});
 document.getElementById('out').textContent=JSON.stringify(r,null,2).slice(0,3000);
 load();
}
load();setInterval(load,5000);
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    server_version = "droid-mcp-console/" + dm.VERSION

    def log_message(self, *a):
        pass

    def _send(self, code, obj, ctype="application/json"):
        body = obj.encode("utf-8") if isinstance(obj, str) else json.dumps(
            obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/status":
            tools = dm.visible_tools()
            return self._send(200, {"version": dm.VERSION, "backend": BE.name,
                                    "read_only": dm.READ_ONLY, "tools": len(tools),
                                    "mutating": sum(1 for t in tools if t["mutating"])})
        if self.path == "/api/tools":
            return self._send(200, {"tools": [
                {"name": t["name"], "description": t["description"],
                 "mutating": t["mutating"]} for t in dm.visible_tools()]})
        if self.path == "/api/log":
            lines, path = [], dm._log_path()
            try:
                with open(path, encoding="utf-8") as f:
                    lines = f.readlines()[-100:]
            except OSError:
                pass
            return self._send(200, {"lines": [ln.strip() for ln in lines if ln.strip()]})
        return self._send(404, {"ok": False})

    def do_POST(self):
        if self.path != "/api/run":
            return self._send(404, {"ok": False})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode() or "{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"ok": False, "error": "坏请求"})
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": body.get("name", ""),
                          "arguments": body.get("args", {})}}
        import time
        t0 = time.time()
        try:
            resp = dm.handle(req, BE)
        except Exception as e:
            resp = {"result": {"content": [{"type": "text", "text": str(e)}],
                                           "isError": True}}
        if isinstance(req, dict):
            dm.log_call(str(body.get("name", "?")),
                        not (resp.get("result") or {}).get("isError", False),
                        int((time.time() - t0) * 1000))
        return self._send(200, resp.get("result", resp))


if __name__ == "__main__":
    print("droid-mcp console → http://127.0.0.1:%d （backend=%s）" % (PORT, BE.name),
          flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
