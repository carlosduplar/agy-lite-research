# antigravity-research-flash-lite

A deterministic `PreToolUse` hook, Python helper script, and agent configuration suite for Google Antigravity that rewrites `invoke_subagent` calls targeting the `research` subagent to `Model: "flash_lite"` (`gemini-3.5-flash-lite`) before execution.

Empirically saves **~2.5x to 2.7x** quota compared to running subagents on default frontier models (`Gemini 4 Hydrogen (High)`).

---

## Why This Hook Is Essential

Antigravity's `invoke_subagent` tool schema defaults its `Model` parameter to `'inherit'` (`['inherit', 'flash_lite', 'flash', 'pro']`). The system prompt instructs parent agents to default to `'inherit'` unless explicitly requested otherwise.

When you work with a frontier model like `Gemini 4 Hydrogen (High)`, any `invoke_subagent` call passing `Model: "inherit"` **overrides the subagent's frontmatter configuration** (e.g. `model: Gemini 3.8 Flash (High)` in `research.md`). As a result, read-heavy exploratory subagent tasks inadvertently inherit and drain your primary frontier model quota.

Because models frequently overlook prompt instructions not to pass `'inherit'`, this lifecycle hook intercepts `invoke_subagent` deterministically at the engine level, replacing `Model` with `"flash_lite"` before the subagent container is launched.

---

## Empirical Benchmark Results (Session `d321135c-6b2d-4187-98a3-d7c5be404512`)

A deterministic 3-way A/B/C benchmark was conducted on an identical, heavy 6-document comparative synthesis task across Antigravity's internal customization documentation (`hooks.md`, `json_configs.md`, `mcp_servers.md`, `plugins.md`, `rules.md`, `skills.md` — ~33KB source text).

Each run invoked `invoke_subagent(TypeName="research", Model="inherit")` after a clean `agy` restart, with live `/usage` quota snapshots measured immediately before and after.

| Metric | Run A (`flash_lite`) | Run B (`inherit`, hook off) | Run C (`flash`) |
| :--- | :--- | :--- | :--- |
| **Subagent Conversation ID** | `9552df30-5676-4835-b137-df1878988bac` | `5033a747-5764-4dc4-a048-9b8a14fcaf78` | `cb4a1972-edc6-4235-a529-8fc171b0cbb9` |
| **Hook Overwrite** | `Model: "flash_lite"` | *(disabled)* | `Model: "flash"` |
| **Observed `PLANNER_RESPONSE.model`** | `gemini-3.5-flash-lite` | `gemini-4-hydrogen-high` | `gemini-4-hydrogen-tiered-high` |
| **Subagent Turns** | `17` *(attempted file writes)* | `5` *(stopped on read-only)* | `5` *(stopped on read-only)* |
| **Input Tokens** | `65,346` | `36,730` | `36,414` |
| **Cache Read Tokens** | `370,039` | `65,718` | `68,698` |
| **Output Tokens** | `11,839` | `14,969` | `15,641` |
| **Weekly Limit Remaining** | `97.83%` &rarr; `97.65%` | `97.45%` &rarr; `97.01%` | `96.67%` &rarr; `96.21%` |
| **Weekly Limit Drain** | **`-0.18%`** | **`-0.44%`** (2.44x Run A) | **`-0.46%`** (2.56x Run A) |
| **5-Hour Limit Remaining** | `93.38%` &rarr; `92.79%` | `92.07%` &rarr; `90.52%` | `89.34%` &rarr; `87.73%` |
| **5-Hour Limit Drain** | **`-0.59%`** | **`-1.55%`** (2.63x Run A) | **`-1.61%`** (2.73x Run A) |

### Key Findings & Discussion

1. **`Model: "flash"` does not save quota vs `inherit`**:
   In current Antigravity deployments, `Model: "flash"` resolves to `gemini-4-hydrogen-tiered-high`. It consumed **2.56x** more Weekly quota and **2.73x** more 5-Hour quota than `flash_lite`, draining virtually the same quota as running on the primary `Gemini 4 Hydrogen (High)` model (`inherit`).
2. **`flash_lite` delivers real quota preservation**:
   Even in an extra-heavy 17-turn run with write retries, `gemini-3.5-flash-lite` consumed less than 40% of the quota drained by `inherit` or `flash`. When properly constrained to return data via `send_message`, a clean 4-turn run consumed only **27,013 input / 28,466 cache read / 3,493 output tokens** (`50dfbfc1-e083-429b-8dae-3548b4142a7d`).
3. **The "Extra Turns" issue and resolution**:
   In Run A, `gemini-3.5-flash-lite` attempted 12 turns of `run_command` script-writing workarounds because the prompt asked to *"Write a manual without sending it back"* while `research` has `enable_write_tools: false`. By contrast, frontier models recognized the contradiction immediately on turn 1.
   - **Fix implemented**: Added explicit boundaries to [`agents/research.md`](./agents/research.md):
     > *"Do not modify or create files. Never attempt to use run_command or scripts to create or write files to disk. Always return all reports, summaries, analyses, and data directly to the caller via send_message."*
   - **Best practice for prompts**: Delegate tasks to `research` with *"Analyze and return via send_message"* instead of *"Write a file"*.

---

## Subagents Architecture (`agents/`)

This repository includes refined definitions for both primary subagents:

### 1. `agents/research.md` (Read-Only Explorer)
- **Role**: Codebase exploration, file search, documentation lookup, and web research.
- **Tools**: Read-only (`enable_write_tools: false`, `enable_mcp_tools: false`).
- **Hook Policy**: **Forced to `flash_lite` via hook**. Massive quota savings with zero risk of code corruption.

### 2. `agents/worker.md` (Mechanical Worker)
- **Role**: Focused edits, lint/format fixes, single-file patches, and narrow test runs.
- **Tools**: Write enabled (`enable_write_tools: true`).
- **Hook Policy**: **NOT forced to `flash_lite`**. `gemini-3.5-flash-lite` has higher error rates on exact-match whitespace diffs (`edit_file`) and recovery loops. To avoid file corruption or looping edits, `worker` remains on `flash` / parent model.
- **Guardrails**: Added strict pre-edit inspection (`read_file` first to copy whitespace byte-for-byte), scoped edits, and an explicit **fail visibly** policy that forbids speculative workarounds.

---

## Script Architecture (`scripts/research-flash-lite.py`)

The standalone Python script [scripts/research-flash-lite.py](./scripts/research-flash-lite.py) replaces earlier inline shell commands:

- **OS-Agnostic & Zero-Quotes**: Operates without complex escaping under Windows `cmd.exe /c`, WSL, Linux `sh -c`, macOS, and Termux.
- **Standard Library Only**: Uses only `json` and `sys`.
- **Configurable Target**: Accepts an optional CLI argument (`sys.argv[1]`) matching `{"flash_lite", "flash", "pro", "inherit"}` (defaults to `"flash_lite"`).
- **Safe Parsing**: Gracefully handles empty stdin or malformed JSON payloads.

```python
# Payload evaluation logic
args = (payload.get("toolCall") or {}).get("args") or {}
if args.get("TypeName") == "research" and args.get("Model") != target_model:
    print(json.dumps({"decision": "allow", "overwrite": {"Model": target_model}}))
else:
    print(json.dumps({"decision": "allow"}))
```

---

## Installation & Setup

### Option 1: Global Hook & Agent Configurations (Recommended)
1. Copy `scripts/research-flash-lite.py` to `~/.agents/scripts/research-flash-lite.py`.
2. Copy `agents/research.md` and `agents/worker.md` to `~/.gemini/config/agents/`.
3. Merge `hooks.json` into `~/.gemini/config/hooks.json`.

### Option 2: Project Workspace Hook
1. Copy `scripts/research-flash-lite.py` to `<project-root>/.agents/scripts/research-flash-lite.py`.
2. Copy `agents/*.md` to `<project-root>/.agents/agents/`.
3. Copy `hooks.json` to `<project-root>/.agents/hooks.json`.

### Option 3: Antigravity Plugin
Clone or copy this repository into your plugins directory:
- Globally: `~/.gemini/config/plugins/antigravity-research-flash-lite/`
- Workspace: `<project-root>/.agents/plugins/antigravity-research-flash-lite/`

The fallback chain in `hooks.json` automatically resolves the script path across all three installation methods:
```json
"command": "python scripts/research-flash-lite.py || python3 scripts/research-flash-lite.py || python ../../.agents/scripts/research-flash-lite.py || python3 ../../.agents/scripts/research-flash-lite.py"
```

> [!IMPORTANT]
> **Restart `agy` after installation**: Antigravity loads and caches `hooks.json` at session startup. Any changes to `hooks.json` require restarting the `agy` server process to take effect.

---

## Requirements

- Python 3.8+ on `PATH` (`python` or `python3`).
- Google Antigravity CLI (`agy`) or Antigravity IDE.
