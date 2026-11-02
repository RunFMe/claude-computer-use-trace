---
title: What Claude sees when it uses your Mac
page_title: What Claude Sees
dek: A computer-use session in the Claude desktop app, logged request by request: what the model receives, what it sends back, and which process presses the button.
meta: November 2026 · Claude desktop app 4.4212 · Claude Code 2.1.309 · macOS 27
---

<!--
How to edit
- Plain Markdown: paragraphs, **bold**, *italic*, `code`, [links](https://example.com), ## headings.
- {#id} after a heading sets its anchor.
- "::: figure NAME" … ":::" places an illustration; the text inside is its caption.
- {{viewer}} places the call-by-call viewer. Its notes are in notes.md.
- "::: appendix TITLE" … ":::" makes a collapsed section.
-->

I noticed that many people, me included, use AI agents without understanding how modern **harnesses** handle more complicated work such as **computer use** or orchestrating subagents. Most people who work with AI know the basic **ReAct loop** behind an agent: the model calls a tool, reads the result and decides on the next call. Fewer know what the companies that build harnesses add on top of that loop. To see it for computer use, I logged one session in the Claude desktop app, request by request.

First, the setup. The **Claude desktop app** runs **Claude Code** (the `claude` CLI) as a separate process, and Claude Code sends the requests to the **Anthropic API**. Inside the desktop app runs an **MCP server** called **`computer-use`**. It sits between the model and macOS: it takes screenshots and presses buttons.

When the model decides to use the computer, it calls the MCP server for a **screenshot** of an app. The **tool result** contains the image and a numbered **element list**: the buttons and fields that the **macOS accessibility API** reports for that window. To click, the model calls another tool with either a number from the list or a pixel coordinate, and the tool result is one line of text that names the element that was pressed.

::: figure core-figure
One step from the logged session. The boxes are the element list drawn onto the image. Claude clicked at (88, 318), the centre of element [14]; the server found the button at that point and pressed it through the macOS accessibility API.
:::

Claude could have passed `element_index: 14` instead of a coordinate; the server would have used the same centre point. In both cases, for a standard control like this one, the server does not send a mouse event. It looks up the **accessibility element** at the point and asks macOS to perform its **press action**, so the tool result can name the button.

The rest of the post has two parts. **Part 1** covers the **scaffolding**, meaning how the model sees the whole interaction, one API request at a time, and the **batching** of actions that let the model run eight actions in one tool call. **Part 2** covers how Claude Code, the API, the desktop app and the MCP server interact.

## 1. The conversation, call by call {#calls}

The model has no separate computer-use mode. Each step is one request to the **Messages API**, and the request contains the **system prompt**, the **tool definitions** and the whole conversation so far in a list called **`messages`**. Claude replies with **tool calls**, Claude Code runs them, and the results are added to `messages` as the next user message. The session took nine calls. For each call, the viewer below shows the request as the JSON object that was sent. The entries added since the previous call are open and highlighted: Claude's reply to the previous request in orange, and the messages that Claude Code added in blue. Read the highlighted comments from top to bottom; each one says what the part of the JSON next to it is. Long strings, the system prompt, the tool definitions and the earlier messages are folded to one line.

{{viewer}}

All of the model's instructions for using the computer are text, in four places: a 6k-character section of computer-use instructions in the **system message**; the 12k-character **skill** that Claude loaded in call 1; the 27 **tool definitions** added in call 2, about 60k characters of descriptions and schemas; and the **tool results**, which include instructions such as "Use the app_* tools to act on it in the background".

Each screenshot result contains both an image and the element list, and Claude used both. It read the label on the clear key from the image before planning its clicks. For buttons in the element list, it clicked the centre of the listed box; the list shows only the first 15 elements, so for 1, 2 and Equals it estimated the position from the grid in the image, for example (34, 375) for a button whose centre is (34, 372). After an action, Claude knows only what the tool result says. It read "84" from the screenshot taken after the batch of clicks; after the last click it had only the one-line result.

### Batching actions {#batching}

**`app_batch`** runs a list of actions inside one tool call. In call 5, Claude sent eight actions, seven clicks and a screenshot, as one `app_batch`, and the server returned all eight results and the new screenshot together 1.0 s later, less time than a person needs to click seven buttons. Sent one at a time, the same actions would have needed eight model calls, and a model call in this session took between 2.5 and 14 s, so the batch saved roughly half a minute. Batching works because the screenshot and the element list let Claude plan all the clicks in advance; it checked the outcome once, in the screenshot at the end of the batch.

## 2. Where it runs {#runs}

On the Mac, a click goes through two processes and one native library, and only Claude Code sends requests to the model.

::: figure process-diagram
Processes involved in one click. The model's tool call (1) goes to Claude Code, which forwards it to the desktop app as a line on its stdout (2). The app passes the same JSON-RPC message to its in-process computer-use server (3), which calls one function in the Swift library (4). That function finds the button through the accessibility API and presses it (5). The tool result is returned the same way and is included in Claude's next request (6).
:::

The desktop app starts a **Claude Code** process for each session and talks to it over that process's **stdin and stdout**, one JSON object per line. Claude Code holds the conversation and the connection to the API. The **computer-use MCP server** is not a separate program: it runs inside the desktop app's own **Electron main process**, built with the Agent SDK's `createSdkMcpServer`, and it calls a Swift library, **`computer_use.node`**, that the app loads directly. When Claude's reply contains `app_click`, Claude Code writes the MCP request to its stdout inside a **control message**, and the app passes the same **JSON-RPC** object to the server in a function call.

The server checks that Calculator is granted and that its window is available, then makes one native call, **`appScoped.probe`**, with the window id, the point (88, 318) and the action. In the library, the accessibility API returns the element at that point and the library performs the element's press action, so the mouse pointer does not move; the faint cursor shown over the app is drawn separately. The result is returned the same way and becomes the tool result in Claude's next request. In the logged run, 154 ms passed between Claude Code sending the request and receiving the result, 77 ms of it in the native call.

**Permissions** are checked in several places. The app pre-approves the computer-use tools for Claude Code, so there is no per-call prompt; the server checks its own **per-app grants** and limits each app by type: browsers can only be viewed, and terminals can be clicked but not typed into. Each API request also includes a server-side **safety check**, and its result for each tool call reaches Claude Code before Claude Code runs the call.

::: appendix Appendix: how this was captured
The installed app can't be inspected directly. Its Electron build disables `RunAsNode`, `NODE_OPTIONS` and `--inspect`, and its code archive is integrity-checked. I made a copy of the app and added logging hooks to its JavaScript: on the Claude Code pipe, on the in-process MCP traffic, and on every call into the Swift library. I also pointed the copy's Claude Code at a local proxy that logs API traffic, then re-signed the copy ad hoc. Electron 44 checks the archive twice, against a hash in `Info.plist` and against a digest of that whole entry stored inside the Electron framework binary, so both had to be updated. The copy ran with its own profile, cloned from the login data of my normal one, and was launched from a terminal so that it inherited that terminal's Screen Recording and Accessibility permissions.

The viewer shows the logged requests with my personal setup removed: my own MCP servers, skills and instructions, my list of installed apps and identifying paths. Everything that ships with Claude is left as it was, including the full computer-use instructions and tool definitions. Token counts are as measured, so they include the removed material.

The scripts and the captured data are in [the GitHub repository](https://github.com/RunFMe/claude-computer-use-trace): [patching and re-signing the copy](https://github.com/RunFMe/claude-computer-use-trace/blob/main/capture/build_cutrace.py), [the logging proxy](https://github.com/RunFMe/claude-computer-use-trace/blob/main/capture/logproxy.py) and [building the viewer data](https://github.com/RunFMe/claude-computer-use-trace/blob/main/capture/make_scaffold.py).
:::

Logged on November 1, 2026. The viewer's data is the real request log of one session, about 400 KB of JSON.
{: .foot}
