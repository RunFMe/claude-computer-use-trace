"""Build docs/ from post/post.md and post/notes.md.

    uv run --with markdown post/build.py           # build once
    uv run --with markdown post/build.py --watch   # rebuild on every save; open the page with ?live to auto-reload
"""
import json, re, shutil, sys, time
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
POST, DOCS = ROOT / "post", ROOT / "docs"
MD_EXT = ["attr_list", "md_in_html"]


def md(text):
    return markdown.markdown(text, extensions=MD_EXT)


def md_inline(text):
    return re.sub(r"^<p>|</p>$", "", md(text.strip()).strip())


def front_matter(text):
    m = re.match(r"---\n([\s\S]*?)\n---\n", text)
    meta = dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)
    return meta, text[m.end():]


VIEWER = '''<div id="scaf" class="scaf bleed">
  <div class="scaf-bar"><button class="prev" aria-label="Previous call">◀</button><div class="chips"></div><button class="next" aria-label="Next call">▶</button></div>
  <div class="note"></div>
  <div class="reqview"></div>
  <div class="raw" hidden></div>
</div>'''


def render_body(text):
    slots = {}

    def slot(html):
        key = f"XSLOTX{len(slots)}X"
        slots[key] = html
        return f"\n\n{key}\n\n"

    text = re.sub(r"<!--[\s\S]*?-->", "", text)

    def block(m):
        kind, arg, inner = m.group(1), m.group(2).strip(), m.group(3)
        if kind == "figure":
            comp = (POST / "components" / f"{arg}.html").read_text()
            return slot(comp.replace("{{caption}}", md_inline(inner)))
        if kind == "appendix":
            return slot(f'<details class="appendix">\n<summary>{md_inline(arg)}</summary>\n{md(inner)}\n</details>')
        raise ValueError(f"unknown block ::: {kind}")

    text = re.sub(r"^::: (\w+) ?(.*)\n([\s\S]*?)^:::\s*$", block, text, flags=re.M)
    text = text.replace("{{viewer}}", slot(VIEWER))
    html = md(text)
    for key, val in slots.items():
        html = html.replace(f"<p>{key}</p>", val)
    return html


def build_notes():
    text = re.sub(r"<!--[\s\S]*?-->", "", (POST / "notes.md").read_text())
    notes, chips = {}, []
    for m in re.finditer(r"^## Call (\d+) · (.+?) · (.+)\n([\s\S]*?)(?=^## Call |\Z)", text, flags=re.M):
        n, title, chip, body = int(m.group(1)), m.group(2).strip(), m.group(3).strip(), m.group(4)
        comments = {}
        cm = re.search(r"^### Comments\n([\s\S]*?)(?=^### |\Z)", body, flags=re.M)
        if cm:
            body = body[:cm.start()] + body[cm.end():]
            for path, text in re.findall(r"^- `([^`]+)` (.+)$", cm.group(1), flags=re.M):
                comments[path.strip()] = md_inline(text)
        parts = re.split(r"^### More: (.+)\n", body, maxsplit=1, flags=re.M)
        main = md(parts[0]).replace("<p>{{meter}}</p>", '<div class="meter-slot"></div>')
        note = {"title": title, "text": main, "comments": comments}
        if len(parts) == 3:
            note["more"] = [parts[1].strip(), md(parts[2]).replace("<p>{{meter}}</p>", '<div class="meter-slot"></div>')]
        notes[n] = note
        chips.append(chip)
    return {"notes": notes, "chips": chips}


def build():
    stamp = str(int(time.time()))
    meta, body = front_matter((POST / "post.md").read_text())
    style = (POST / "style.css").read_text()
    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{meta.get("page_title", meta["title"])}</title>
<style>
{style}</style>
<link rel="stylesheet" href="scaffold.css?v={stamp}">
</head>
<body>
<main>

<h1>{md_inline(meta["title"])}</h1>
<p class="dek">{md_inline(meta["dek"])}</p>
<p class="meta">{md_inline(meta["meta"])}</p>

{render_body(body)}
</main>
<script>window.BUILD = "{stamp}";</script>
<script src="scaffold.js?v={stamp}"></script>
<script>
if (new URLSearchParams(location.search).has("live")) setInterval(() => fetch("build-id.txt", {{cache: "no-store"}}).then(r => r.text()).then(t => {{ if (t.trim() !== window.BUILD) location.reload(); }}).catch(() => {{}}), 1000);
</script>
</body>
</html>
'''
    (DOCS / "index.html").write_text(page)
    (DOCS / "notes.json").write_text(json.dumps(build_notes(), ensure_ascii=False))
    shutil.copyfile(ROOT / "data" / "requests.json", DOCS / "scaffold.json")
    for f in ("scaffold.js", "scaffold.css"):
        shutil.copyfile(POST / "viewer" / f, DOCS / f)
    (DOCS / "build-id.txt").write_text(stamp)
    print(time.strftime("%H:%M:%S"), "built docs/index.html")


def sources():
    files = [*POST.rglob("*.md"), *POST.rglob("*.html"), *POST.rglob("*.css"), *POST.rglob("*.js"), ROOT / "data" / "requests.json"]
    return {f: f.stat().st_mtime for f in files if f.exists()}


if __name__ == "__main__":
    build()
    if "--watch" in sys.argv:
        seen = sources()
        while True:
            time.sleep(0.5)
            now = sources()
            if now != seen:
                seen = now
                try:
                    build()
                except Exception as e:  # keep watching after a typo
                    print("build failed:", e)
