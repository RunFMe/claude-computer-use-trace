"""Logging reverse proxy for api.anthropic.com. Writes one JSON file per request; secrets redacted."""
import http.client, http.server, json, os, sys, time, itertools, threading

UPSTREAM = "api.anthropic.com"
LOGDIR = sys.argv[1]
PORT = int(sys.argv[2])
SECRET = ("authorization", "x-api-key", "cookie", "set-cookie", "proxy-authorization")
counter = itertools.count(1)
lock = threading.Lock()

def redact(headers):
    return {k: ("<redacted>" if k.lower() in SECRET or "token" in k.lower() else v) for k, v in headers}

def parse(b):
    try:
        return json.loads(b)
    except Exception:
        return b.decode("utf-8", "replace")

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _body(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            out = b""
            while True:
                n = int(self.rfile.readline().strip(), 16)
                if n == 0:
                    self.rfile.readline(); return out
                out += self.rfile.read(n); self.rfile.readline()
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))
    def _go(self):
        with lock:
            n = next(counter)
        t0 = time.time()
        body = self._body()
        hdrs = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "accept-encoding", "content-length", "transfer-encoding", "connection")}
        hdrs["Accept-Encoding"] = "identity"
        conn = http.client.HTTPSConnection(UPSTREAM, timeout=600)
        conn.request(self.command, self.path, body=body or None, headers=hdrs)
        r = conn.getresponse()
        self.send_response(r.status)
        for k, v in r.getheaders():
            if k.lower() not in ("transfer-encoding", "connection", "content-length", "content-encoding"):
                self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        chunks = []
        while True:
            c = r.read1(65536)
            if not c:
                break
            chunks.append(c)
            self.wfile.write(b"%x\r\n%s\r\n" % (len(c), c)); self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
        rec = {"n": n, "t": t0, "ms": int((time.time() - t0) * 1000), "method": self.command, "path": self.path,
               "req_headers": redact(self.headers.items()), "req_body": parse(body) if body else None,
               "status": r.status, "resp_headers": redact(r.getheaders()), "resp_body": b"".join(chunks).decode("utf-8", "replace")}
        with open(os.path.join(LOGDIR, f"{n:04d}-{self.command}-{self.path.split('?')[0].strip('/').replace('/', '_')}.json"), "w") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _go

http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
