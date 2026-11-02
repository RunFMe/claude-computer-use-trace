"""Scripted stand-in for the Messages API. Logs every request; answers the main loop with a fixed tool-use script.

Usage: python3 fakeapi.py log_dir 8791
"""
import http.server, json, os, sys, itertools, uuid

LOGDIR, PORT = sys.argv[1], int(sys.argv[2])
counter = itertools.count(1)


def sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def message(blocks, stop):
    mid = "msg_fake_" + uuid.uuid4().hex[:12]
    ev = [{"type": "message_start", "message": {"id": mid, "type": "message", "role": "assistant", "model": "scripted",
           "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 1}}}]
    for i, b in enumerate(blocks):
        if b["type"] == "text":
            ev += [{"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}},
                   {"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": b["text"]}}]
        else:
            js = json.dumps(b["input"])
            ev += [{"type": "content_block_start", "index": i, "content_block": {"type": "tool_use", "id": b["id"], "name": b["name"], "input": {}}}]
            ev += [{"type": "content_block_delta", "index": i, "delta": {"type": "input_json_delta", "partial_json": js[k:k + 20]}} for k in range(0, len(js), 20)]
        ev.append({"type": "content_block_stop", "index": i})
    ev += [{"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 20}},
           {"type": "message_stop"}]
    full = {"id": mid, "type": "message", "role": "assistant", "model": "scripted", "content": blocks, "stop_reason": stop,
            "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 20}}
    return ev, full


APP = "com.apple.calculator"
SCRIPT = [
    ([{"type": "tool_use", "id": "toolu_fake_00", "name": "ToolSearch",
       "input": {"query": "select:mcp__cu-mirror__app_screenshot,mcp__cu-mirror__app_click", "max_results": 2}}], "tool_use"),
    ([{"type": "text", "text": "I'll look at Calculator first."},
      {"type": "tool_use", "id": "toolu_fake_01", "name": "mcp__cu-mirror__app_screenshot", "input": {"app": APP}}], "tool_use"),
    ([{"type": "tool_use", "id": "toolu_fake_02", "name": "mcp__cu-mirror__app_click",
       "input": {"app": APP, "element_index": 9, "action_summary": "Presses the 7 key"}}], "tool_use"),
    ([{"type": "text", "text": "Pressed 7."}], "end_turn"),
]


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("request-id", "req_fake"); self.end_headers(); self.wfile.write(body)

    def _go(self):
        n = next(counter)
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            req = json.loads(raw) if raw else None
        except Exception:
            req = raw.decode("utf-8", "replace")
        reply, kind = None, "other"
        if self.path.startswith("/v1/messages") and "count_tokens" not in self.path and isinstance(req, dict):
            tools = [t.get("name", "") for t in req.get("tools", [])]
            if "ToolSearch" in tools and "Press 7 in Calculator" in json.dumps(req.get("messages", [])):
                kind = "main"
                step = min(sum(1 for m in req["messages"] if m["role"] == "assistant"), len(SCRIPT) - 1)
                blocks, stop = SCRIPT[step]
            else:
                kind = "side"
                blocks, stop = [{"type": "text", "text": "ok"}], "end_turn"
            ev, full = message(blocks, stop)
            if req.get("stream"):
                reply = sse(ev); self._send(200, reply, "text/event-stream")
            else:
                reply = json.dumps(full).encode(); self._send(200, reply, "application/json")
        elif "count_tokens" in self.path:
            reply = b'{"input_tokens": 1000}'; self._send(200, reply, "application/json")
        else:
            reply = b'{"type":"error","error":{"type":"not_found_error","message":"fake api"}}'; self._send(404, reply, "application/json")
        hdr = {k: ("<redacted>" if k.lower() in ("authorization", "x-api-key") else v) for k, v in self.headers.items()}
        with open(os.path.join(LOGDIR, f"{n:04d}-{kind}-{self.command}-{self.path.split('?')[0].strip('/').replace('/', '_')}.json"), "w") as f:
            json.dump({"n": n, "kind": kind, "method": self.command, "path": self.path, "req_headers": hdr, "req_body": req,
                       "resp_body": reply.decode("utf-8", "replace")}, f, ensure_ascii=False, indent=1)

    do_GET = do_POST = _go


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
