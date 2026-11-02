"""Build the data for the scaffold stepper from the main-loop requests of one traced session.

Usage: python3 make_scaffold.py <api-log dir> <out.json> <req id> [<req id> ...]
Every string is redacted: home paths, the scratchpad prefix, email addresses (except example/noreply),
and the account/org UUIDs passed in REDACT_UUIDS.
"""
import json, os, re, sys

A, OUT, IDS = sys.argv[1], sys.argv[2], sys.argv[3:]
HOME = os.path.expanduser("~")
USER = os.path.basename(HOME)
REDACT_UUIDS = [u for u in os.environ.get("REDACT_UUIDS", "").split(",") if u]
KEEP_EMAILS = ("@example.com", "noreply@anthropic.com")


def red(s):
    s = re.sub(r"/private/tmp/claude-\d+/[^\s\"'\\]*?/scratchpad", "<scratchpad>", s)
    s = s.replace(HOME, "~").replace(f"-Users-{USER}-", "-Users-you-").replace(USER, "you")
    s = re.sub(r"[\w.+-]+@[\w-]+\.[A-Za-z][\w.]*", lambda m: m.group(0) if m.group(0).endswith(KEEP_EMAILS) else "you@example.com", s)
    for i, u in enumerate(REDACT_UUIDS):
        s = s.replace(u, ["<account-uuid>", "<org-uuid>"][min(i, 1)])
    return s


def deep(o):
    if isinstance(o, str):
        return red(o)
    if isinstance(o, list):
        return [deep(x) for x in o]
    if isinstance(o, dict):
        return {k: deep(v) for k, v in o.items() if k != "cache_control"}
    return o


def load(i):
    return json.load(open(os.path.join(A, f"{i}-POST-v1_messages.json")))


def parse_sse(body):
    msg, blocks, partial = {}, {}, {}
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        ev = json.loads(line[6:])
        t = ev["type"]
        if t == "message_start":
            msg = ev["message"]
        elif t == "content_block_start":
            blocks[ev["index"]] = dict(ev["content_block"]); partial[ev["index"]] = ""
        elif t == "content_block_delta":
            d, b = ev["delta"], blocks[ev["index"]]
            if d["type"] == "text_delta": b["text"] = b.get("text", "") + d["text"]
            elif d["type"] == "input_json_delta": partial[ev["index"]] += d["partial_json"]
            elif d["type"] == "thinking_delta": b["thinking"] = b.get("thinking", "") + d["thinking"]
            elif d["type"] == "signature_delta": b["signature"] = b.get("signature", "") + d["signature"]
        elif t == "content_block_stop":
            b = blocks[ev["index"]]
            if b["type"] == "tool_use": b["input"] = json.loads(partial[ev["index"]] or "{}")
        elif t == "message_delta":
            msg["stop_reason"] = ev["delta"].get("stop_reason")
            msg["safeguard_results"] = ev["delta"].get("safeguard_results")
            msg.setdefault("usage", {}).update(ev.get("usage") or {})
    content = [blocks[k] for k in sorted(blocks)]
    for b in content:
        b.pop("caller", None)
    return msg, content


recs = [load(i) for i in IDS]
final_req = recs[-1]["req_body"]
messages = deep(final_req["messages"])
last_msg, last_content = parse_sse(recs[-1]["resp_body"])
messages.append({"role": "assistant", "content": deep(last_content)})

tools = {}
for r in recs:
    for t in r["req_body"]["tools"]:
        tools[t["name"]] = deep({k: t[k] for k in ("description", "input_schema", "defer_loading") if k in t})

steps = []
for i, r in zip(IDS, recs):
    b = r["req_body"]
    marks = [f"system[{si}]" for si, sb in enumerate(b["system"]) if sb.get("cache_control")]
    for mi, m in enumerate(b["messages"]):
        if isinstance(m["content"], list):
            marks += [[mi, bi] for bi, bb in enumerate(m["content"]) if bb.get("cache_control")]
    msg, _ = parse_sse(r["resp_body"])
    u = msg.get("usage", {})
    sg = (msg.get("safeguard_results") or [{}])[0].get("status", {}).get("tool_uses", {})
    params = {k: b[k] for k in ("model", "max_tokens", "stream", "thinking", "output_config", "context_management") if k in b}
    params["safeguards"] = [{"type": b["safeguards"][0]["type"], "classifier_context": "{… " + str(len(b["safeguards"][0]["classifier_context"])) + " keys: permission_mode, platform, live_cwd, rules, git_state, prior_turn_context …}"}] if b.get("safeguards") else None
    params["metadata"] = {"user_id": "{device_id, account_uuid, session_id} (redacted)"}
    hdr = {k: v for k, v in r["req_headers"].items() if k.lower() in ("anthropic-beta", "anthropic-version", "user-agent", "x-app")}
    steps.append({
        "req": i, "ms": r["ms"], "n_msgs": len(b["messages"]), "tools": [t["name"] for t in b["tools"]],
        "marks": marks, "params": deep(params), "headers": hdr, "stop_reason": msg.get("stop_reason"),
        "usage": {k: u.get(k) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")},
        "safeguard": {k: v.get("outcome") for k, v in sg.items()},
        "bytes": len(json.dumps(b)),
    })

data = {"system": [red(s["text"]) for s in final_req["system"]], "tools": tools, "messages": messages, "steps": steps}
json.dump(data, open(OUT, "w"), ensure_ascii=False)
print("messages", len(messages), "tools", len(tools), "steps", len(steps), "json bytes", os.path.getsize(OUT))
