# What Claude sees when it uses your Mac

The post, its data, and the scripts used to capture a computer-use session in the Claude desktop app
(Claude desktop 4.4212, Claude Code 2.1.309, Electron 44.9.3, macOS 27).

## Layout

| Path | Contents |
| --- | --- |
| `post/post.md` | The article text, in Markdown |
| `post/notes.md` | The per-call notes shown in the viewer |
| `post/components/` | The two figures (HTML/SVG); their captions are in `post.md` |
| `post/viewer/` | The call-by-call viewer (`scaffold.js`, `scaffold.css`) |
| `post/style.css`, `post/build.py` | Page styles and the build script |
| `docs/` | The built site (generated; do not edit by hand) |
| `docs/tweets/` | Thread draft and the five 1600×900 images |
| `data/requests.json` | Run 1: the nine Messages API requests of the traced session shown in the post |
| `data/run-2/` | Run 2, the same task recaptured: `requests.json` (same format) and `wire.jsonl`, the log of the other three boundaries |
| `capture/` | Scripts used to capture and prepare the data |

## Editing and building the post

```bash
uv run --with markdown post/build.py --watch
```

Edit `post/post.md` or `post/notes.md` and save; the site in `docs/` is rebuilt on every save. Serve `docs/` (for example `python3 -m http.server -d docs 8770`) and open the page with `?live` to reload it automatically after each build.

To publish, run `post/publish.sh "Commit message"`: it rebuilds `docs/`, commits everything and pushes, and GitHub Pages serves the new version about a minute later. With `BLOCKLIST=<file of private terms>` set, it refuses to push when a changed file contains one of them.

Markers in `post.md`:

- `::: figure core-figure` … `:::` and `::: figure process-diagram` … `:::` place the figures; the text inside is the caption.
- `{{viewer}}` places the viewer.
- `::: appendix Title` … `:::` makes a collapsed section.
- `{#id}` after a heading sets its anchor; `{: .foot}` after a paragraph applies a class.

In `notes.md`, each call is a section headed `## Call N · Title · Chip`, where Chip is the label on the step button; `### More: Title` adds a collapsed detail section, and `{{meter}}` places the token chart. `### Comments` lists comments as ``- `json.path` text``; each is drawn above that value in the request (paths such as `tools`, `messages[3].content[2]`, `response.stop_reason`), and a commented block is never folded.

## Data

`data/requests.json` has four keys:

- `system`: the three system blocks, identical in every request.
- `tools`: every tool definition that appeared in any request (74).
- `messages`: the 18 messages of the last request followed by Claude's final reply, 19 entries in all. Request N contains the first `steps[N-1].n_msgs` entries.
- `steps`: one entry per API call: request size, number of messages, tool names, cache breakpoint positions, parameters, selected headers, latency, token usage, stop reason and safeguard verdicts.

Removed or replaced before publishing:

- Authorization headers and the OAuth token (never written to disk by the logging proxy).
- The author's own MCP servers, skills, plugins, agent types and CLAUDE.md instructions; only components that ship with Claude remain.
- The installed-apps list in the `request_access` and `request_teach_access` schemas, replaced with stock macOS apps.
- Home paths, the email address, account and organization IDs, and the device ID in `metadata.user_id`.
- Thinking-block signatures (replaced with their length) and the local file paths of saved screenshots.
- Metadata in the screenshots (EXIF, Photoshop and ICC profile blocks) and the display's model name; the image data itself is unchanged.

Token counts in `steps[].usage` are as measured, so they include the removed material.

## Capture scripts

| Script | Purpose |
| --- | --- |
| `capture/build_cutrace.py` | Patches a copy of Claude.app with logging hooks on four boundaries (API base URL, Claude Code stdin/stdout, in-process MCP JSON-RPC, calls into `computer_use.node`), rewrites `app.asar` with new integrity hashes, and updates both integrity pins (`Info.plist` and the digest in the Electron framework). Re-sign the copy afterwards with `codesign --force --deep --sign -`. |
| `capture/logproxy.py` | Logging reverse proxy for `api.anthropic.com`; writes one JSON file per request with auth headers redacted. |
| `capture/make_scaffold.py` | Turns the proxy's logs of the main-loop requests into the viewer data. |
| `capture/clean_wire.py` | Reduces a raw boundary log to computer-use traffic and removes personal data. |
| `capture/asar_extract.py` | Extracts files from an `app.asar` for reading. |
| `capture/trace_cu.py` | Prints the computer-use tool calls and results from a Claude Code transcript. |
| `capture/standin/host.py`, `fakeapi.py` | A minimal stand-in for the desktop app and a scripted Messages API, used to observe the stdin/stdout control protocol with the real Claude Code binary. |

### Reproducing a capture

1. `cp -c -R /Applications/Claude.app ClaudeCUTrace.app` (APFS clone), then `python3 capture/build_cutrace.py ClaudeCUTrace.app` and `codesign --force --deep --sign - ClaudeCUTrace.app`.
2. Start `python3 capture/logproxy.py api-log 8790`.
3. Prepare a profile folder containing only the login-related parts of `~/Library/Application Support/Claude` (cookies, local storage, preferences, `config.json`, `claude-code/`) and a `claude_desktop_config.json` with `"chicagoEnabled": true`.
4. From a terminal that already has Screen Recording and Accessibility permission, run the copy's binary with `CUTRACE_USER_DATA=<profile> CUTRACE_LOG=<wire.jsonl> CUTRACE_BASE_URL=http://127.0.0.1:8790`.
5. Run a computer-use task in the copy's Code tab, then build the data with `make_scaffold.py`.

The copy shares `~/.claude` with the installed app's Claude Code; quit it when you are done.

## Run 2 and the boundary log

`data/run-2/` is a second run of the same prompt, captured after the first run's boundary logs were lost. Its `requests.json` has the same format as run 1. `wire.jsonl` has one JSON object per line, `{"n", "t", "w", "d"}`, where `t` is a Unix time in milliseconds and `w` names the boundary and direction:

| `w` | Boundary |
| --- | --- |
| `② app→cli`, `② cli→app` | Claude Code's stdin and stdout. Kept: `mcp_message` and `hook_callback` control requests about computer use, the responses to them, assistant and user messages that contain computer-use calls or results, and the final `result` line. Claude Code writes each control response back to its stdout, so each response appears twice. |
| `③ sdk→server`, `③ server→sdk` | JSON-RPC between the app's Agent SDK and its in-process computer-use MCP server. |
| `④ js→native`, `④ native→js` | Every call into `computer_use.node`, with arguments, result and duration. |

Removed from the log: session setup (`initialize`, `mcp_set_servers` and their responses), all other MCP servers' traffic, installed and running app lists (replaced by their length), every app name other than Calculator and Claude, paths, emails and UUIDs. The image data in screenshot results was shortened by the logger when it was written.

In run 2, the `app_click` on 5 took 117 ms from Claude Code's `tools/call` to the result, 43 ms of it in `appScoped.probe`, and the `app_batch` took 685 ms; these are the timings quoted in the post.
