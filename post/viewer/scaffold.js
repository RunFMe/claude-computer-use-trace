// Viewer: steps through the real Messages API requests of one computer-use session.
// Each request is drawn as the JSON body that was sent; each entry of "messages" is shown as its own object.
(() => {
  const root = document.getElementById("scaf");
  if (!root) return;
  const V = window.BUILD || "";

  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = n => (n ?? 0).toLocaleString("en-US");
  const short = (s, n) => (s.length > n ? s.slice(0, n) + "…" : s);
  const bare = n => n.replace(/^mcp__.*?__/, "");

  // ---------- JSON rendering ----------
  const P = s => `<span class="jp">${s}</span>`;
  const KEY = k => `<span class="jk">"${esc(k)}"</span>`;
  const COMMA = P(",");
  const isScalar = v => v === null || typeof v !== "object";
  const LONG = 1600; // strings longer than this show their first lines and fold the rest

  // Comments from notes.md for the current call, keyed by JSON path ("messages[3].content[2]").
  // A comment is drawn after the value's opening bracket, or after the value when it fits on one line.
  let CM = {};
  const cmt = path => (CM[path] ? ` <em class="cnote">// ${CM[path]}</em>` : "");
  const hasNote = path => Object.keys(CM).some(k => k === path || k.startsWith(path + ".") || k.startsWith(path + "["));

  // Folded parts are rendered only when opened; REG holds a function per fold.
  let REG = [];
  function fold(collapsed, why, tail, render, cls = "") {
    REG.push(render);
    return `<details class="jfold ${cls}"><summary><span class="tw"></span>${collapsed}${tail}${why ? `<span class="why">// ${esc(why)}</span>` : ""}</summary><div class="jmb" data-reg="${REG.length - 1}"></div></details>`;
  }

  // the first few lines of a long string
  function headOf(s) {
    let end = 0, n = 0;
    while (n < 7) {
      const k = s.indexOf("\n", end);
      if (k < 0 || k > 700) {
        const sp = s.lastIndexOf(" ", 700);
        return s.slice(0, sp > end ? sp : 700); // the budget ends inside a line: cut at a space
      }
      if (s.slice(end, k).trim()) n++;
      end = k + 1;
    }
    return s.slice(0, end);
  }
  function strHTML(s, tail = "") {
    if (/^<[^<>]{1,120}>$/.test(s)) return `<span class="jph">${esc(s)}</span>${tail}`; // placeholders such as <signature removed, …>
    if (s.length <= LONG) return `<span class="js">"${esc(s)}"</span>${tail}`;
    const head = headOf(s), rest = s.slice(head.length);
    const why = `${fmt(rest.length)} more characters${rest.includes("## computer-use") ? ", including the computer-use instructions" : ""}`;
    return `<span class="js">"${esc(head)}</span>` + fold(`<span class="js">…"</span>`, why, tail, () => `<span class="js">${esc(rest)}"</span>${tail}`, "inl str");
  }
  function scalarHTML(v) {
    if (v === null) return `<span class="jl">null</span>`;
    if (typeof v === "boolean") return `<span class="jl">${v}</span>`;
    if (typeof v === "number") return `<span class="jnum">${v}</span>`;
    return strHTML(v);
  }
  function fitsInline(v) {
    if (isScalar(v)) return !(typeof v === "string" && (v.length > 70 || v.includes("\n")));
    if (!Array.isArray(v) && v.type === "image") return false;
    const kids = Array.isArray(v) ? v : Object.values(v);
    return kids.every(fitsInline) && JSON.stringify(v).length <= 96;
  }
  function inlineHTML(v) {
    if (isScalar(v)) return scalarHTML(v);
    if (Array.isArray(v)) return v.length ? P("[") + v.map(inlineHTML).join(P(", ")) + P("]") : P("[]");
    const e = Object.entries(v);
    return e.length ? P("{") + e.map(([k, x]) => `${KEY(k)}${P(": ")}${inlineHTML(x)}`).join(P(", ")) + P("}") : P("{}");
  }
  // tail is appended after the closing bracket (a comma between siblings); path is the value's JSON path
  function jsonHTML(v, tail = "", path = "") {
    if (typeof v === "string") return strHTML(v, tail) + cmt(path);
    if (isScalar(v)) return scalarHTML(v) + tail + cmt(path);
    if (fitsInline(v)) return inlineHTML(v) + tail + cmt(path);
    if (Array.isArray(v)) {
      const item = (x, i) => `<div>${jsonHTML(x, i < v.length - 1 ? COMMA : "", `${path}[${i}]`)}</div>`;
      // long uniform lists (tool_reference blocks): the first rows, then the rest folded
      const cut = v.length > 10 && v.every(x => !isScalar(x) && x.type === v[0].type) ? 4 : v.length;
      const more = cut < v.length ? `<div>${fold("", `${v.length - cut} more ${v[0].type ? `"${v[0].type}" blocks` : "items"}`, "", () => v.slice(cut).map((x, i) => item(x, cut + i)).join(""))}</div>` : "";
      return P("[") + cmt(path) + `<div class="ji">${v.slice(0, cut).map(item).join("")}${more}</div>` + P("]") + tail;
    }
    if (v.type === "image" && v.source && v.source.data && v.source.data.length > 200) {
      const shown = { ...v, source: { ...v.source, data: `<${fmt(v.source.data.length)} characters of base64 ${v.source.media_type}, shown below>` } };
      return jsonHTML(shown, tail, path) + `<img class="jimg" alt="the image in this content block" src="data:${v.source.media_type};base64,${v.source.data}">`;
    }
    return P("{") + cmt(path) + `<div class="ji">${entriesHTML(Object.entries(v), path)}</div>` + P("}") + tail;
  }
  function entriesHTML(e, path) {
    return e.map(([k, x], i) => `<div>${KEY(k)}${P(": ")}${jsonHTML(x, i < e.length - 1 ? COMMA : "", `${path}.${k}`)}</div>`).join("");
  }
  // one-line stand-in for a collapsed object
  function collapsedHTML(v, note) {
    if (Array.isArray(v)) return `${P("[")} <span class="jc">${esc(note)}</span> ${P("]")}`;
    const head = Object.entries(v).filter(([k, x]) => isScalar(x) && (typeof x !== "string" || x.length <= 60)).slice(0, 2);
    return P("{") + head.map(([k, x]) => `${KEY(k)}${P(": ")}${scalarHTML(x)}`).join(P(", ")) + (note ? `${head.length ? P(", ") : ""}<span class="jc">${esc(note)}</span>` : "") + P("}");
  }

  // ---------- messages: fold what the step is not about ----------
  let toolNames = {};
  function textOf(c) { return typeof c === "string" ? c : (c || []).filter(x => x.type === "text").map(x => x.text).join(" "); }
  function contentHTML(blocks, tail, path) {
    const items = blocks.map((b, i) => `<div>${jsonHTML(b, i < blocks.length - 1 ? COMMA : "", `${path}[${i}]`)}</div>`).join("");
    return P("[") + cmt(path) + `<div class="ji">${items}</div>` + P("]") + tail;
  }
  function messageHTML(m, tail, path) {
    const rest = Object.entries(m).filter(([k]) => k !== "role" && k !== "content"), ct = rest.length ? COMMA : "";
    const content = typeof m.content === "string" ? strHTML(m.content, ct) : contentHTML(m.content, ct, `${path}.content`);
    return P("{") + cmt(path) + `<div class="ji"><div>${KEY("role")}${P(": ")}${scalarHTML(m.role)}${COMMA}</div><div>${KEY("content")}${P(": ")}${content}</div>${entriesHTML(rest, path)}</div>` + P("}") + tail;
  }
  function messageSummary(m) {
    if (typeof m.content === "string") return "environment, MCP server instructions, tool names, skills";
    return m.content.map(b => {
      if (b.type === "text") return b.text.startsWith("<system-reminder>") ? "reminder" : m.role === "assistant" ? "text" : `"${short(b.text.replace(/\s+/g, " "), 30)}"`;
      if (b.type === "tool_use") return `${bare(b.name)}()`;
      if (b.type === "tool_result") return `result of ${bare(toolNames[b.tool_use_id] || "?")}${(Array.isArray(b.content) ? b.content : []).some(x => x.type === "image") ? " with screenshot" : ""}`;
      return b.type;
    }).join(", ");
  }

  // ---------- request pieces ----------
  function withMarks(m, i, marks) {
    if (!Array.isArray(m.content)) return m;
    const c = m.content.map((b, bi) => marks.some(x => Array.isArray(x) && x[0] === i && x[1] === bi) ? { ...b, cache_control: { type: "ephemeral" } } : b);
    return { role: m.role, content: c };
  }
  function systemBlocks(marks) {
    return DATA.system.map((t, i) => (marks.includes(`system[${i}]`) ? { type: "text", text: t, cache_control: { type: "ephemeral" } } : { type: "text", text: t }));
  }

  function meterHTML(st) {
    const tot = s => s.usage.cache_read_input_tokens + s.usage.cache_creation_input_tokens + s.usage.input_tokens;
    const max = Math.max(...DATA.steps.map(tot));
    return `<div class="meter">${DATA.steps.map((s, k) => {
      const u = s.usage, w = v => (100 * v / max).toFixed(2) + "%";
      return `<div class="mrow${k + 1 === st ? " on" : ""}"><span class="ml">${k + 1}</span><span class="mbar"><span class="seg rd" style="width:${w(u.cache_read_input_tokens)}"></span><span class="seg wr" style="width:${w(u.cache_creation_input_tokens + u.input_tokens)}"></span></span><span class="mv">${fmt(tot(s))}</span></div>`;
    }).join("")}</div>`;
  }

  let DATA = null, NOTES = null, current = 1;

  function render(st) {
    REG = [];
    const S = DATA.steps[st - 1], prevN = st > 1 ? DATA.steps[st - 2].n_msgs : 0, N = NOTES.notes[st], u = S.usage;
    const last = st === DATA.steps.length, total = u.cache_read_input_tokens + u.cache_creation_input_tokens + u.input_tokens;

    root.querySelector(".note").innerHTML = `<h3><span class="num">Call ${st}</span> ${esc(N.title)}</h3>${N.text}${N.more ? `<details class="moreinfo"><summary>${esc(N.more[0])}</summary>${N.more[1]}</details>` : ""}`;
    root.querySelectorAll(".meter-slot").forEach(s => (s.innerHTML = meterHTML(st)));

    CM = N.comments || {};
    const params = Object.entries(S.params).map(([k, v]) => `<div>${KEY(k)}${P(": ")}${jsonHTML(v, COMMA, k)}</div>`).join("");
    const badge = (m, i) => m.role === "assistant" ? `generated by Claude: its reply to request ${st - 1}` : i === 0 ? "added by Claude Code: reminders and the prompt" : m.role === "system" ? "added by Claude Code" : "added by Claude Code: tool results";
    const items = DATA.messages.slice(0, S.n_msgs).map((m, i) => {
      const isNew = i >= prevN, tail = i < S.n_msgs - 1 ? COMMA : "", p = `messages[${i}]`;
      const msg = withMarks(m, i, S.marks);
      return `<div class="jm r-${m.role}${isNew ? " isnew" : ""}" data-mi="${i}"><span class="gut">[${i}]</span>${isNew || hasNote(p)
        ? `<div class="jmb">${messageHTML(msg, tail, p)}</div>${isNew ? `<span class="badge">${badge(m, i)}</span>` : ""}`
        : fold(collapsedHTML({ role: m.role }, typeof m.content === "string" ? `"content": ${fmt(m.content.length)}-character string` : `"content": [${m.content.length} blocks]`), messageSummary(m), tail, () => messageHTML(msg, tail, p))}</div>`;
    }).join("");
    // Claude's reply appears as a message in the next request; only the last reply is shown on its own.
    const reply = DATA.messages[S.n_msgs];
    const responseHTML = last ? messageHTML({ role: "assistant", content: reply.content, stop_reason: S.stop_reason }, "", "response") : "";

    root.querySelector(".reqview").innerHTML = `
<div class="frame">
  <div class="fhead"><span class="verb">POST</span> /v1/messages <span class="dim">· request ${st} of ${DATA.steps.length} · ${fmt(S.bytes)} bytes · input ${fmt(total)} tokens, ${(100 * u.cache_read_input_tokens / total).toFixed(1)}% from the prompt cache</span></div>
  <div class="jroot">${P("{")}<div class="ji">
    ${params}
    <div>${KEY("system")}${P(": ")}<details class="jfold inl" data-part="system"><summary><span class="tw"></span>${collapsedHTML([], `3 text blocks: billing header, identity line, ${fmt(DATA.system[2].length)}-character core prompt`)}${COMMA}${cmt("system")}</summary><div class="jmb"></div></details></div>
    <div>${KEY("tools")}${P(": ")}<details class="jfold inl" data-part="tools"><summary><span class="tw"></span>${collapsedHTML([], `${S.tools.length} tool definitions${st === 2 ? ", 27 of them new in this request" : ""}`)}${COMMA}${cmt("tools")}</summary><div class="jmb"></div></details></div>
    <div>${KEY("messages")}${P(": [")} <span class="jc">${S.n_msgs} entries${st > 1 ? `, ${S.n_msgs - prevN} added since request ${st - 1}` : ""}</span>${cmt("messages")}</div>
    <div class="jlist">${items}</div>
    <div>${P("]")}</div>
  </div>${P("}")}</div>
</div>
${last
  ? `<div class="arrow">Claude's reply to this request. Its stop_reason is end_turn, so Claude Code sends no further request.</div>
<div class="frame resp r-assistant"><div class="jroot">${responseHTML}</div></div>`
  : ""}`;

    root.querySelectorAll(".chipstep").forEach(b => b.classList.toggle("on", +b.dataset.step === st));
    const strip = root.querySelector(".chips"), on = strip.querySelector(".on");
    if (on && (on.offsetLeft < strip.scrollLeft || on.offsetLeft + on.offsetWidth > strip.scrollLeft + strip.clientWidth))
      strip.scrollLeft = on.offsetLeft - (strip.clientWidth - on.offsetWidth) / 2;
    root.querySelector(".prev").disabled = st === 1;
    root.querySelector(".next").disabled = last;
    current = st;
  }

  root.addEventListener("click", e => {
    const t = e.target.closest("button");
    if (!t || !DATA) return;
    if (t.classList.contains("prev") && current > 1) render(current - 1);
    else if (t.classList.contains("next") && current < DATA.steps.length) render(current + 1);
    else if (t.dataset.step) render(+t.dataset.step);
  });
  // Fill folded parts only when they are opened: older messages, system blocks, tool definitions.
  root.addEventListener("toggle", e => {
    const d = e.target;
    if (!(d instanceof HTMLDetailsElement) || !d.open || !d.classList.contains("jfold")) return;
    const body = d.querySelector(":scope > .jmb");
    if (body.innerHTML) return;
    if (body.dataset.reg !== undefined) { body.innerHTML = REG[+body.dataset.reg](); return; }
    const S = DATA.steps[current - 1];
    if (d.dataset.part === "system") body.innerHTML = jsonHTML(systemBlocks(S.marks), COMMA, "system");
    else if (d.dataset.part === "tools") body.innerHTML = P("[") + `<div class="ji">${S.tools.map((n, i) => `<details class="jfold tool"><summary><span class="tw"></span>${collapsedHTML({ name: n }, "…")}${i < S.tools.length - 1 ? COMMA : ""}</summary><div class="jmb" data-tool="${esc(n)}" data-tail="${i < S.tools.length - 1 ? 1 : ""}"></div></details>`).join("")}</div>` + P("],");
    else if (d.classList.contains("tool")) {
      const n = body.dataset.tool;
      body.innerHTML = jsonHTML({ name: n, ...DATA.tools[n] }, body.dataset.tail ? COMMA : "");
    }
  }, true);
  document.addEventListener("keydown", e => {
    if (!DATA || !root.matches(":hover")) return;
    if (e.key === "ArrowRight" && current < DATA.steps.length) render(current + 1);
    if (e.key === "ArrowLeft" && current > 1) render(current - 1);
  });

  Promise.all([fetch(`scaffold.json?v=${V}`).then(r => r.json()), fetch(`notes.json?v=${V}`).then(r => r.json())]).then(([D, N]) => {
    DATA = D; NOTES = N;
    D.messages.forEach(m => Array.isArray(m.content) && m.content.forEach(b => { if (b.type === "tool_use") toolNames[b.id] = b.name; }));
    root.querySelector(".chips").innerHTML = D.steps.map((s, k) => `<button class="chipstep" data-step="${k + 1}" title="${esc(N.notes[k + 1].title)}"><b>${k + 1}</b> ${esc(N.chips[k])}</button>`).join("");
    const m = location.hash.match(/^#call-([1-9])$/);
    render(m && +m[1] <= D.steps.length ? +m[1] : 1);
    if (m) root.scrollIntoView();
  }).catch(err => { root.querySelector(".note").textContent = "Could not load the viewer data: " + err; });
})();
