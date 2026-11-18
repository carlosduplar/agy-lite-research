# antigravity-research-flash-lite

A deterministic `PreToolUse` hook (and Antigravity plugin) that rewrites any `invoke_subagent` call targeting the built-in `research` subagent to `Model: "flash_lite"` (`gemini-3.5-flash-lite`) before execution.

## Why

Antigravity's built-in `research` subagent defaults to `Model: "inherit"`, which consumes your primary model's quota (for example, `Gemini 4 Hydrogen (High)`) during repo searches and file-reading loops. Built-in subagents do not expose an editable `agent.md` config file, so this hook intercepts `invoke_subagent` deterministically and injects `"Model": "flash_lite"` when `TypeName == "research"`.

## How It Works

`hooks.json` registers a `PreToolUse` hook matching `invoke_subagent`:
- Reads the hook payload JSON from `stdin`.
- If `toolCall.args.TypeName == "research"` and `Model != "flash_lite"`, returns:
  ```json
  {
    "decision": "allow",
    "overwrite": {
      "Model": "flash_lite"
    }
  }
  ```
- Otherwise returns `{"decision": "allow"}`.

## Installation

Choose one of the following:

### Option 1: Global Hook
Copy `hooks.json` to `~/.gemini/config/hooks.json` (merge under the top-level object if you already have hooks configured).

### Option 2: Workspace Hook
Copy `hooks.json` to `<project-root>/.agents/hooks.json`.

### Option 3: Antigravity Plugin
Place this repository directory under `~/.gemini/config/plugins/antigravity-research-flash-lite/` or `<project-root>/.agents/plugins/antigravity-research-flash-lite/`.

Start a new session (or restart `agy`) after installing, as Antigravity loads `hooks.json` at session startup.

## Requirements

- `python3` available on `PATH`.
