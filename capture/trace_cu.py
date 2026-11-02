"""Print the computer-use tool calls and results recorded in a Claude Code transcript.

Usage: python3 trace_cu.py [path/to/session.jsonl]
With no argument, picks the most recent transcript under ~/.claude/projects that has a computer-use call.
"""
import glob
import json
import os
import sys

PREFIX = "mcp__computer-use__"


def find_latest():
    paths = sorted(glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")), key=os.path.getmtime, reverse=True)
    for p in paths:
        with open(p, errors="ignore") as f:
            if PREFIX in f.read():
                return p
    sys.exit("no transcript with computer-use calls found")


def describe(parts):
    if isinstance(parts, str):
        parts = [{"type": "text", "text": parts}]
    out = []
    for p in parts:
        if p.get("type") == "image":
            src = p["source"]
            out.append(f"  [image {src.get('media_type')} ~{len(src.get('data', '')) * 3 // 4} bytes]")
        else:
            out.append("  " + p.get("text", "").replace("\n", "\n  "))
    return "\n".join(out)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else find_latest()
    print(f"# {path}\n")
    names = {}
    for line in open(path):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        content = (rec.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if b.get("type") == "tool_use" and b.get("name", "").startswith(PREFIX):
                names[b["id"]] = b["name"][len(PREFIX):]
                print(f"{rec.get('timestamp', '')} >> {names[b['id']]} {json.dumps(b['input'])}")
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in names:
                print(f"{rec.get('timestamp', '')} << {names[b['tool_use_id']]}")
                print(describe(b.get("content")) + "\n")


if __name__ == "__main__":
    main()
