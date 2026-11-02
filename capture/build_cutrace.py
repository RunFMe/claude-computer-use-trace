"""Patch a copy of Claude.app's app.asar with logging on four wires and rewrite the asar + integrity hash.

Usage: python3 build_cutrace.py <path/to/Copy.app>
Logging only happens when the CUTRACE_LOG env var is set; the API is redirected only when CUTRACE_BASE_URL is set.
"""
import hashlib, json, plistlib, struct, sys, os

APP = sys.argv[1]
ASAR = os.path.join(APP, "Contents/Resources/app.asar")
PLIST = os.path.join(APP, "Contents/Info.plist")
BLOCK = 4 * 1024 * 1024

LOGGER = r'''globalThis.__cutrace||=(()=>{const f=process.env.CUTRACE_LOG;if(!f)return()=>{};const fs=require("fs");
const rep=(k,v)=>{if(v&&typeof v==="object"){if(v instanceof Uint8Array)return`<binary ${v.length} bytes>`;if(v.type==="Buffer"&&Array.isArray(v.data))return`<binary ${v.data.length} bytes>`}
if(typeof v==="string"&&v.length>4000)return v.slice(0,800)+`…<${v.length} chars total>`;if(typeof v==="function")return"<function>";if(typeof v==="bigint")return v.toString();return v};
let n=0;return(w,d)=>{try{if(typeof d==="string"&&d[0]==="{")try{d=JSON.parse(d)}catch{}fs.appendFileSync(f,JSON.stringify({n:++n,t:Date.now(),w,d},rep)+"\n")}catch(e){try{fs.appendFileSync(f,JSON.stringify({n:++n,t:Date.now(),w,err:String(e)})+"\n")}catch{}}}})();
globalThis.__cutraceWrap||=(root)=>{const T=globalThis.__cutrace;let seq=0;const cache=new WeakMap();
const wrap=(o,path)=>{if(cache.has(o))return cache.get(o);const p=new Proxy(o,{get(t,k){const v=Reflect.get(t,k,t);if(typeof k!=="string")return v;const name=path+"."+k;
if(typeof v==="function")return function(...a){const id=++seq,t0=Date.now();T("④ js→native",{id,fn:name,args:a});let r;try{r=v.apply(t,a)}catch(e){T("④ native→js",{id,fn:name,ms:Date.now()-t0,threw:String(e)});throw e}
if(r&&typeof r.then==="function")return r.then(x=>(T("④ native→js",{id,fn:name,ms:Date.now()-t0,result:x}),x),e=>{T("④ native→js",{id,fn:name,ms:Date.now()-t0,rejected:String(e)});throw e});
T("④ native→js",{id,fn:name,ms:Date.now()-t0,result:r});return r};
if(v&&typeof v==="object")return wrap(v,name);return v}});cache.set(o,p);return p};return wrap(root,"computerUse")};
'''

PATCHES = {
    ".vite/build/index.chunk-CZxSNxKH.js": [
        # wire ②, app -> CLI stdin
        ("write(e){if(this.abortController.signal.aborted)throw Q7();",
         'write(e){globalThis.__cutrace("② app→cli",e);if(this.abortController.signal.aborted)throw Q7();'),
        # wire ②, CLI stdout -> app
        ("for await(let t of e)if(t.trim()){let e;try{e=pd(t)}",
         'for await(let t of e)if(t.trim()){globalThis.__cutrace("② cli→app",t);let e;try{e=pd(t)}'),
        # wire ③, SDK -> in-process MCP server
        ("if(this.pendingMcpResponses.set(r,{resolve:t=>{a(),e(t)},reject:e=>{a(),i(e)}}),n.onmessage)n.onmessage(t.message);",
         'if(this.pendingMcpResponses.set(r,{resolve:t=>{a(),e(t)},reject:e=>{a(),i(e)}}),n.onmessage)(globalThis.__cutrace("③ sdk→server",{server:t.server_name,msg:t.message}),n.onmessage(t.message));'),
        # wire ③, in-process MCP server -> SDK
        ("sendMcpServerMessageToCli(e,t){",
         'sendMcpServerMessageToCli(e,t){globalThis.__cutrace("③ server→sdk",{server:e,msg:t});'),
    ],
    ".vite/build/index.chunk-m4oMImJ-.js": [
        # wire ④, every call into computer_use.node
        ("return nea=e.computerUse,nea", "return nea=globalThis.__cutraceWrap(e.computerUse),nea"),
        # wire ①, point the spawned CLI at a local logging proxy when asked
        ('Qi("CLAUDE_E2E_INFERENCE_BASE_URL")||e.apiHost', "process.env.CUTRACE_BASE_URL||e.apiHost"),
    ],
}


def integrity(data):
    blocks = [hashlib.sha256(data[i:i + BLOCK]).hexdigest() for i in range(0, max(len(data), 1), BLOCK)]
    return {"algorithm": "SHA256", "hash": hashlib.sha256(data).hexdigest(), "blockSize": BLOCK, "blocks": blocks}


with open(ASAR, "rb") as f:
    _, hsize, _, jlen = struct.unpack("<4I", f.read(16))
    header = json.loads(f.read(jlen))
    base = 8 + hsize
    blob = f.read()

entries = []
def walk(node, path):
    for name, ent in node.get("files", {}).items():
        p = f"{path}/{name}" if path else name
        if "files" in ent:
            walk(ent, p)
        elif "offset" in ent and not ent.get("unpacked"):
            entries.append((p, ent))
walk(header, "")
entries.sort(key=lambda pe: int(pe[1]["offset"]))

out, pos = [], 0
for path, ent in entries:
    off = int(ent["offset"])
    data = blob[off: off + ent["size"]]
    if path in PATCHES:
        text = data.decode("utf-8")
        for old, new in PATCHES[path]:
            assert text.count(old) == 1, f"anchor not unique in {path}: {old[:60]}"
            text = text.replace(old, new)
        assert text.startswith('"use strict";'), path
        text = text.replace('"use strict";', '"use strict";' + LOGGER, 1)
        data = text.encode("utf-8")
        ent["integrity"] = integrity(data)
        print(f"patched {path}: {len(PATCHES[path])} anchors, {ent['size']} -> {len(data)} bytes")
    elif path == ".vite/build/index.pre.js":
        # The app scrubs CLAUDE_USER_DATA_DIR unless a signed dev token is present, so move userData
        # (and logs) ourselves before any app code runs. The app name stays "Claude", which keeps the
        # Keychain "Claude Safe Storage" key usable for a cloned profile.
        text = data.decode("utf-8")
        assert text.startswith('"use strict";'), path
        early = ('if(process.env.CUTRACE_USER_DATA){const __a=require("electron").app,__d=process.env.CUTRACE_USER_DATA;'
                 '__a.setPath("userData",__d);__a.setAppLogsPath(require("path").join(__d,"Logs"))}')
        data = text.replace('"use strict";', '"use strict";' + early, 1).encode("utf-8")
        ent["integrity"] = integrity(data)
        print("patched index.pre.js: userData from CUTRACE_USER_DATA")
    ent["offset"] = str(pos)
    ent["size"] = len(data)
    out.append(data)
    pos += len(data)

hjson = json.dumps(header, separators=(",", ":")).encode("utf-8")
pad = (4 - len(hjson) % 4) % 4
hsize = 4 + 4 + len(hjson) + pad
with open(ASAR, "wb") as f:
    f.write(struct.pack("<4I", 4, hsize, hsize - 4, len(hjson)))
    f.write(hjson + b"\0" * pad)
    for d in out:
        f.write(d)

with open(PLIST, "rb") as f:
    pl = plistlib.load(f)
pl["ElectronAsarIntegrity"]["Resources/app.asar"]["hash"] = hashlib.sha256(hjson).hexdigest()
pl["CFBundleIdentifier"] = "com.anthropic.claudefordesktop.cutrace"
pl["CFBundleDisplayName"] = "Claude CU Trace"
pl.pop("CFBundleURLTypes", None)  # never register claude:// or msauth:// for the copy
with open(PLIST, "wb") as f:
    plistlib.dump(pl, f)
print("asar rewritten; header sha256", hashlib.sha256(hjson).hexdigest())

# Electron 44 also pins a digest of the whole ElectronAsarIntegrity dictionary inside the framework binary
# (section __DATA_CONST,__asar_integrity: 32-byte sentinel, used, version, 32-byte sha256).
FW = os.path.realpath(os.path.join(APP, "Contents/Frameworks/Electron Framework.framework/Electron Framework"))
SENTINEL = b"AGbevlPCksUGKNL8TSn7wGmJEuJsXb2A"
d = hashlib.sha256()
for key in sorted(pl["ElectronAsarIntegrity"]):
    d.update(key.encode()); d.update(pl["ElectronAsarIntegrity"][key]["algorithm"].encode()); d.update(pl["ElectronAsarIntegrity"][key]["hash"].encode())
with open(FW, "r+b") as f:
    fw = f.read()
    assert fw.count(SENTINEL) == 1, "integrity sentinel not unique"
    i = fw.find(SENTINEL)
    assert fw[i + 32] == 1 and fw[i + 33] == 1, "unexpected integrity struct layout"
    f.seek(i + 34); f.write(d.digest())
print("framework integrity digest", d.hexdigest())
