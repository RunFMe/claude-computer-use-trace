<!--
Notes shown in the viewer, one per API call.
"## Call N · Title · Chip" — Chip is the short label on the step button.
"### More: Title" — a collapsed detail section under the note.
"### Comments" — one line per comment: - `json.path` text. The comment is drawn after that value's opening bracket
   (or after the value, when it fits on one line); an older message with a comment is shown open. Paths: params by name (safeguards), system, tools, messages[i],
   messages[i].content[j], nested .content[k], and for the last call response.content[j], response.stop_reason.
   Say who does what ("Model asks for …", "Harness returns …", "MCP server returns …" for computer-use results); do not restate the role, type or tool name.
{{meter}} inside a section places the per-call token chart.
-->

## Call 1 · Initial request · Start

The first request already contains three **system blocks**, 47 **tool definitions** and two **messages**. The first message is the prompt, preceded by three **reminders** added by the harness: the user's email, commit attribution rules, and a note about the scratch folder. The second message has role **`system`** and is 34k characters long. It describes the environment and contains each MCP server's instructions, including a 6k-character section on computer use.

None of the 47 tools is a computer-use tool. Their names appear only in a list of **deferred tools**. Claude's reply, the first message added in call 2, loads the computer-use **skill** and calls **`ToolSearch`** to get the tool definitions.

### Comments

- `safeguards` Anthropic checks the model's tool calls; the response returns a verdict per call, for every call except ToolSearch in this session
- `system` System prompt: the same in every request, with nothing about computer use
- `tools` No computer-use tools yet
- `messages[0]` Harness adds three reminders before the user's request
- `messages[0].content[3]` User asks for a calculation in the Calculator app
- `messages[1]` Mid-conversation system message with descriptions of the MCP servers, one of which is the computer-use server

### More: Why the tools are deferred

Claude Code sends MCP tools by name only until the model requests them; one `DeferredToolPlaceholder` entry represents all of them. The 27 computer-use tools have about 60k characters of descriptions and schemas, and the app has other MCP servers as well. Sending all schemas in every request would add thousands of tokens to each call, including in sessions that never use the screen.

## Call 2 · Tool definitions added · Tools

Two messages are new. The first is Claude's reply to call 1: it loads the skill and calls `ToolSearch`. The second holds the tool results. The skill result is 12k characters of text appended to the message. The `ToolSearch` result is 27 **`tool_reference`** blocks and no text, and in the same request the tools array grows from 47 to 74 definitions.

### Comments

- `tools` Harness adds the definitions of the 27 computer-use tools
- `messages[2].content[0]` Model thinks; the text is not in the log
- `messages[2].content[1]` Model creates a task list in the desktop app
- `messages[2].content[2]` Model loads the computer-use skill
- `messages[2].content[3]` Model asks for the computer-use tool definitions
- `messages[3].content[0]` Harness confirms the task list is shown
- `messages[3].content[1]` Harness confirms the skill launched
- `messages[3].content[2]` Harness makes the 27 computer-use tools callable
- `messages[3].content[3]` Harness adds the skill's text: how to use the computer
- `messages[3].content[4]` Harness confirms the tools are loaded

### More: What a tool_reference does

The 27 new definitions are in the request's `tools` array with `defer_loading: true`. A `tool_reference` block marks the point in the conversation where a definition becomes visible to the model. Before a reference appears, the model has only the tool's name.

## Call 3 · Access granted · Access

Claude's first computer-use call is `request_access` for Calculator. The user saw an **approval dialog** while it was running. The result is JSON: Calculator is granted at **tier** `"full"`, screenshots are filtered natively, and a field says that the user prefers background control.

### Comments

- `messages[4].content[0]` Model requests approval for using Calculator app
- `messages[4].content[1]` Update task list again
- `messages[5].content[0]` After approval, the harness returns that the use was approved
- `messages[5].content[1]` Harness confirms the task list update

## Call 4 · open_application · Open

Claude calls `open_application`. The result is a sentence: *"Calculator is already running with a reachable window. Use the app_\* tools to act on it in the background."* Many results have this form: a status, then an instruction for the next step.

### Comments

- `messages[6].content[0]` Model asks MCP server to open Calculator
- `messages[7].content[0]` MCP server reports that Calculator is open and says which tools to use next

## Call 5 · First screenshot · Screenshot

Claude calls `app_screenshot`. The result has three blocks: a 230×461 JPEG, a line that Claude Code adds after saving the image to disk, and the server's text. The text gives the window id and an **accessibility summary** (the element list) with one line per clickable element: its number, role, box and title.

### Comments

- `messages[8].content[0]` Model asks MCP server for a screenshot of Calculator's window
- `messages[8].content[1]` Update task list again
- `messages[9].content[0]` MCP server returns the screenshot
- `messages[9].content[0].content[0]` Screenshot of the window; click coordinates use its pixels
- `messages[9].content[0].content[1]` Path where the harness saved the image
- `messages[9].content[0].content[2]` Clickable elements from the accessibility API, with their positions
- `messages[9].content[1]` Harness confirms the task list update

### More: Image size and coordinates

The image is Calculator's window at 230×461 pixels. The boxes in the element list and the coordinates in Claude's clicks use this image's pixels: element [14] has its corner at (64, 294) and a size of 48×48, so its centre is (88, 318).

## Call 6 · Batch of seven clicks · Batch

Claude's reply uses both the image and the element list. It states from the image that the clear key shows "C", then sends seven clicks and a screenshot in one **`app_batch`** call. The result contains, for each action, a header and a one-line result such as `ok (AXPress on AXButton '7' …)`, followed by a second screenshot showing 84. All seven clicks were performed as accessibility **press actions**, including the clicks given as coordinates.

### Comments

- `messages[10].content[0]` Model thinks; the text is not in the log
- `messages[10].content[1]` Model reads the clear key from the image
- `messages[10].content[2]` Model asks MCP server for seven clicks and a screenshot in one call
- `messages[11].content[0]` MCP server returns the results of all eight actions
- `messages[11].content[0].content[1]` Each click pressed a named button through the accessibility API
- `messages[11].content[0].content[15]` Screenshot after the batch, showing 84
- `messages[11].content[0].content[17]` Updated list of clickable elements
- `messages[11].content[0].content[18]` All eight actions succeeded

## Call 7 · Click on 5 · Click

Claude reads 84 from the second screenshot and clicks 5 at (88, 318), the centre of element [14]. The result of the click is one line: `ok (AXPress on AXButton '5' via AXWindow>AXGroup>AXSplitGroup>AXGroup×2)`. This line is the **only information** the model gets about the action; to check the effect it would need another screenshot. Part 2 describes how this click was processed.

### Comments

- `messages[12].content[0]` Model reads 84 from the screenshot
- `messages[12].content[1]` Model asks MCP server to click 5 at the centre of element [14] from the list in call 5
- `messages[12].content[2]` Update task list again
- `messages[13].content[0]` MCP server reports which button was pressed, without a screenshot
- `messages[13].content[1]` Harness confirms the task list update

## Call 8 · Releasing the app · Release

Claude calls `app_release`, and the result is "All app locks released."

### Comments

- `messages[14].content[0]` Model asks MCP server to release Calculator
- `messages[15].content[0]` MCP server confirms the release

## Call 9 · Final reply · Reply

Claude calls `wrap_up`, a desktop-app tool that can show a next-step box under the chat. Nothing was pending, so the result says no box is drawn and tells Claude to write its closing message. The reply to this request is text with `stop_reason: "end_turn"`, so Claude Code sends no further request. The last request contained 18 messages and both screenshots, about 108k input tokens. From call 3 on, all but a few dozen to about two thousand tokens of each request were read from the **prompt cache**.

### Comments

- `messages[16].content[0]` Model sends a recap to the desktop app; with nothing pending, no box is drawn
- `messages[17].content[0]` Harness tells the model to write its closing message
- `response.content[0]` Model's final answer to the user
- `response.stop_reason` No tool calls, so the loop ends

### More: Why resending everything is cheap

The API keeps no state between calls, so Claude Code sends the whole conversation in every request. **Cache breakpoints** on the system prompt and on the two newest messages let the API reuse everything up to the end of the previous request. Each bar is one call's input: grey was read from the cache, orange was written to it.

{{meter}}
