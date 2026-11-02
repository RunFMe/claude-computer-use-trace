"""Extract files under a path prefix from an Electron app.asar (read-only).

Usage: python3 asar_extract.py /Applications/Claude.app/Contents/Resources/app.asar out_dir .vite/build
"""
import json, os, struct, sys

src, out, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src, "rb") as f:
    _, hsize, _, jlen = struct.unpack("<4I", f.read(16))
    header = json.loads(f.read(jlen))
    base = 8 + hsize

    def walk(node, path):
        for name, ent in node.get("files", {}).items():
            p = f"{path}/{name}" if path else name
            if "files" in ent:
                walk(ent, p)
            elif p.startswith(prefix) and "offset" in ent and not ent.get("unpacked"):
                f.seek(base + int(ent["offset"]))
                data = f.read(ent["size"])
                dst = os.path.join(out, p)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, "wb").write(data)

    walk(header, "")
