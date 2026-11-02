"""Reduce a cutrace wire.jsonl to the computer-use traffic and remove personal data.

Usage: python3 clean_wire.py wire.jsonl out.jsonl [private-blocklist.txt]

Keeps:
  ② Claude Code stdin/stdout: control messages about computer-use tools (mcp_message, hook_callback, can_use_tool),
     assistant/user messages that contain computer-use tool calls or results, and the final result line.
  ③ in-process MCP: messages to and from the computer-use server.
  ④ native calls into computer_use.node: all of them.
Removes or replaces: app names and bundle ids other than Calculator and Claude, installed-app lists, home paths,
the session folder path, emails, UUIDs, and anything listed in the private blocklist.
"""
import json, os, re, sys

SRC, OUT = sys.argv[1], sys.argv[2]
BLOCK = [l.strip() for l in open(sys.argv[3]) if l.strip()] if len(sys.argv) > 3 else []
HOME = os.path.expanduser("~")
KEEP_APPS = re.compile(r"^(com\.apple\.calculator|Calculator|com\.anthropic\.claudefordesktop.*|Claude)$")
STOCK_APPS = "App Store, Calculator, Calendar, Contacts, Finder, FaceTime, Mail, Maps, Messages, Music, Notes, Photos, Preview, Reminders, Safari, System Settings, Terminal, TextEdit"
APP_KEYS = {"bundleId", "displayName", "name", "path", "localizedName", "appName", "bundleIdentifier", "rawTitle", "title"}  # native-call results only
LIST_FNS = ("apps.listInstalled", "apps.listInstalledWithRunning", "apps.listRunning", "apps.resolveBundleIds",
            "apps.previewHideSet", "apps.iconDataUrl")
uuids = {}


def red_str(s):
    s = re.sub(r"<installed-apps>[\s\S]*?</installed-apps>", f"<installed-apps>{STOCK_APPS}</installed-apps>", s)
    s = re.sub(r"/private/tmp/claude-\d+/[^\s\"'\\]*", "<tmp>", s)
    s = re.sub(re.escape(HOME) + r"/Library/Application Support/Claude/scratch-workspaces/[^\s\"'\\]*", "<session-folder>", s)
    s = s.replace(HOME, "~").replace("-Users-" + os.path.basename(HOME) + "-", "-Users-you-")
    s = re.sub(r"[\w.+-]+@[\w-]+\.[A-Za-z][\w.]*", lambda m: m.group(0) if m.group(0).endswith(("@example.com", "noreply@anthropic.com")) else "you@example.com", s)
    s = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", lambda m: uuids.setdefault(m.group(0), f"<uuid-{len(uuids) + 1}>"), s)
    for b in BLOCK:
        s = re.sub(re.escape(b), "<removed>", s, flags=re.I)
    return s


def red(o, key=None, apps=False):
    if isinstance(o, str):
        if apps and key in APP_KEYS and not KEEP_APPS.match(o) and not o.startswith("<"):
            return "<other app>"
        return red_str(o)
    if isinstance(o, list):
        return [red(x, key, apps) for x in o]
    if isinstance(o, dict):
        return {k: red(v, k, apps) for k, v in o.items()}
    return o


def mentions_cu(o):
    return "computer-use" in json.dumps(o)


out, kept_ids = [], set()
KEEP_REQUESTS = {"mcp_message", "hook_callback", "can_use_tool"}
for line in open(SRC):
    try:
        r = json.loads(line)
    except ValueError:
        continue
    w, d = r["w"], r.get("d")
    if w.startswith("④"):
        if any(d.get("fn", "").endswith(f) or f in d.get("fn", "") for f in LIST_FNS) and "result" in d:
            res = d["result"]
            n = len(res.get("apps", res)) if isinstance(res, dict) else len(res) if isinstance(res, list) else None
            d = {**d, "result": f"<list of {n} apps removed>" if n is not None else "<removed>"}
        out.append({**r, "d": red(d, apps=True)})
    elif w.startswith("③"):
        if isinstance(d, dict) and d.get("server") == "computer-use":
            out.append({**r, "d": red(d)})
    elif w.startswith("②") and isinstance(d, dict):
        t = d.get("type")
        if t == "result":
            out.append({**r, "d": red({k: d.get(k) for k in ("type", "subtype", "duration_ms", "duration_api_ms", "num_turns", "stop_reason", "usage")})})
        elif t == "control_request":
            # only the per-call traffic; session setup (initialize, mcp_set_servers, …) carries the user's configuration
            if (d.get("request") or {}).get("subtype") in KEEP_REQUESTS and mentions_cu(d):
                kept_ids.add(d.get("request_id"))
                out.append({**r, "d": red(d)})
        elif t == "control_response":
            if (d.get("response") or {}).get("request_id") in kept_ids:
                out.append({**r, "d": red(d)})
        elif t in ("assistant", "user") and mentions_cu(d):
            out.append({**r, "d": red(d)})

with open(OUT, "w") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
s = open(OUT).read()
print("kept", len(out), "events;", {k: sum(1 for r in out if r["w"].startswith(k)) for k in "②③④"},
      "| blocklist hits left:", [b for b in BLOCK if b.lower() in s.lower()] or "none")
