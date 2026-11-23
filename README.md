# antigravity-research-flash-lite

A deterministic `PreToolUse` hook, Python helper script, and agent configuration suite for Google Antigravity that rewrites `invoke_subagent` calls targeting **only the `research` subagent** to `Model: "flash_lite"` (`gemini-3.5-flash-lite`) before execution.

> [!NOTE]
> **Scope of savings**: Quota savings apply **strictly to delegated `research` subagent calls** (`TypeName="research"`). Your primary session turns, `worker` edits, `self` subagents, and non-`research` tool calls continue consuming your selected frontier model quota as usual. Actual overall session savings depend on how much read-heavy exploration you delegate to `research`.

On fresh single-dispatch `agy -p` `research` benchmarks (Gemini AI Pro), routing `research` calls to `flash_lite` reduces the `research` subagent's own quota drain to **`< 0.01%` (`0.00%` measured)** — cutting benchmark-run drain by **2.67x** on **Gemini 4 Hydrogen (High)**, **4.26x** on **Gemini 4 Neon (High)**, **3.26x** on **Gemini 4 Argon (High)**, and keeping **Claude Opus 5.5 (Medium)** subagent drain at **0.00%**.

![Research Subagent Quota Drain Comparison](./assets/benchmark-savings.svg)

---

## Why This Hook Is Essential

Antigravity's `invoke_subagent` tool schema defaults its `Model` parameter to `'inherit'` (`['inherit', 'flash_lite', 'flash', 'pro']`). The system prompt instructs parent agents to default to `'inherit'` unless explicitly requested otherwise.

When your main session uses a frontier model such as `Gemini 4 Hydrogen (High)`, `Gemini 4 Neon (High)`, `Gemini 4 Argon (High)`, or `Claude Opus 5.5 (Medium)`, any `invoke_subagent(TypeName="research", Model="inherit")` call **overrides `research.md`'s frontmatter model** (`model: flash_lite`). As a result, read-heavy exploratory `research` calls inadvertently inherit and drain your primary frontier model quota.

Because parent models frequently overlook prompt instructions not to pass `'inherit'`, this lifecycle hook intercepts `invoke_subagent` deterministically at the engine level, replacing `Model` with `"flash_lite"` **only when `TypeName == "research"`**. Other subagents (`worker`, `self`, etc.) are left untouched.

---

## Empirical Benchmark Results (`research` Subagent Only)

A deterministic multi-model A/B benchmark was conducted on a **Gemini AI Pro** subscription using fresh, isolated `agy -p --model <id>` sessions (zero leftover conversation history) on a single heavy 6-document comparative synthesis task delegated to `research` across Antigravity's internal customization documentation (`hooks.md`, `json_configs.md`, `mcp_servers.md`, `plugins.md`, `rules.md`, `skills.md` — ~33KB source text).

Each run invoked `invoke_subagent(TypeName="research", Model="inherit")` with live `/usage` quota snapshots measured immediately before and after that single `agy -p` dispatch. *(Percentage drains reflect a **Gemini AI Pro** quota pool and scale with your subscription tier.)*

| Metric | Run A (`flash_lite`, Plugin ON) | Run B — Hydrogen High (`inherit`) | Run B — Neon High (`inherit`) | Run B — Argon High (`inherit`) |
| :--- | :--- | :--- | :--- | :--- |
| **Observed `PLANNER_RESPONSE.model`** | `gemini-3.5-flash-lite` | `gemini-4-hydrogen-high` | `gemini-4-neon-high` | `gemini-4-argon-high` |
| **Benchmark-Run Quota Multiplier Savings** | **Baseline (`0.00%` / `< 0.01%` `research` drain)** | **2.20x Weekly / 2.67x 5-Hr lower run drain** (`-0.05% / -0.15%` ON vs `-0.11% / -0.40%` OFF) | **4.22x Weekly / 4.26x 5-Hr lower run drain** (`-0.09% / -0.31%` ON vs `-0.38% / -1.32%` OFF) | **3.26x lower Argon run drain** (`-0.38%` ON vs `-1.24%` OFF; **`0.00%` Argon** subagent drain) |

### Key Findings & Discussion

1. **Near-zero `research` subagent quota consumption (`< 0.01%`)**:
   In both **Argon (High)** and **Claude Opus 5.5 (Medium)** Plugin ON runs (where parent turns billed against Argon or Claude pools while `research` ran on `gemini-3.5-flash-lite`), the General Weekly (`89.00%`) and 5-Hour (`93.81%`) counters moved **`0.00%`**. Thus a `flash_lite` `research` subagent call consumes `< 0.01%` of General quota and **`0.00%`** of Argon or Claude/GPT quota.
2. **Argon & Claude pool preservation (`0.00%` subagent drain)**:
   When working with `Gemini 4 Argon (High)`, disabling the plugin raised total Argon Weekly drain from **`-0.38%`** (parent-only) to **`-1.24%`** (**3.26x** higher), meaning the unhooked `research` subagent alone consumed **`-0.86%`** of weekly Argon quota. With **Claude Opus 5.5 (Medium)** + Plugin ON, parent turns consumed `-3.70%` Weekly / `-7.39%` 5-Hour Claude quota while `research` ran on `flash_lite` with **`0.00%`** Claude quota drain *(Plugin OFF skipped to preserve remaining Claude quota)*.
3. **Fresh-session A/B multipliers on `Hydrogen` (`2.67x`) & `Neon` (`4.26x`)**:
   In isolated `agy -p` single-dispatch runs (one parent turn delegating to `research`), enabling the plugin reduced 5-Hour drain from `-0.40%` to `-0.15%` (**2.67x**, Weekly `-0.11%` → `-0.05%` = **2.20x**) on `Gemini 4 Hydrogen (High)`, and from `-1.32%` to `-0.31%` (**4.26x**, Weekly `-0.38%` → `-0.09%` = **4.22x**) on `Gemini 4 Neon (High)`. These multipliers reflect a `research`-heavy single dispatch; sessions with fewer `research` calls or heavy parent/worker coding will see proportionally smaller overall savings.
4. **Hardened `agents/research.md` configuration**:
   The plugin also includes a hardened `agents/research.md` definition with explicit read-only instructions (`enable_write_tools: false`, return strictly via `send_message`). As observed during benchmarking, this prevents `research` from attempting tool workarounds on ambiguous tasks. Meanwhile, `agents/worker.md` intentionally remains unhooked on `flash` / parent model.

### Estimated Overall Session Impact

> [!IMPORTANT]
> The measured benchmark multipliers above apply **to `research` subagent dispatches ONLY**—primary parent turns, `worker`, and `self` subagents still bill against your selected model quota.

Because Google does not publish an Antigravity-wide breakdown of `research` vs. main-agent quota usage, total session impact depends on how much of your workflow is delegated to `research` rather than handled directly by the parent agent. Grounded in Microsoft's [*FastContext* paper](https://arxiv.org/abs/2606.14066) (**46.5%** of main-agent tokens and **56.2%** of tool turns spent reading/searching code), scaling the measured per-model `research` multipliers gives:

- **Small repos / targeted edits** (~10% `research` share): estimated total gains of **~22% on Hydrogen**, **~32% on Argon**, and **~44% on Neon**.
- **Unfamiliar repos / exploration-heavy workflows** (~50% `research` share): estimated total gains up to **~1.1x on Hydrogen**, **~1.63x on Argon**, and **~2.1x on Neon** *(plus secondary prompt-cache savings from keeping bulky reads out of the parent context)*.

Common **exploration-heavy workflows** that benefit most from delegating discovery to `research` include:
- **QA & bug triage**: reproducing symptoms, tracing execution paths, and inspecting logs/stack traces.
- **Code audits & security reviews**: scanning auth boundaries, data flows, and configuration surfaces across modules.
- **PR validation & impact analysis**: checking cross-file callers, breaking changes, and test coverage before merging.
- **Unfamiliar codebase onboarding**: mapping repository architecture, entry points, and conventions.
- **Large-scale refactoring discovery**: locating all symbol usages and edge cases before running edits.
- **Dependency, API & documentation synthesis**: comparing internal specs, schemas, or third-party SDK usage across files.

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

## Installation & Setup

### Option 1: Antigravity Plugin (Recommended)
Install directly from GitHub via the Antigravity CLI:
```bash
agy plugin install https://github.com/carlosduplar/antigravity-research-flash-lite
```

Or clone locally and install from the directory (via CLI or `/plugin install <directory>` inside `agy`):
```bash
git clone https://github.com/carlosduplar/antigravity-research-flash-lite.git
agy plugin install ./antigravity-research-flash-lite
```

Verify installation with `agy plugin list`.

### Option 2: Global Hook & Agent Configurations
1. Copy `scripts/research-flash-lite.py` to `~/.agents/scripts/research-flash-lite.py`.
2. Copy `agents/research.md` and `agents/worker.md` to `~/.gemini/config/agents/`.
3. Merge `hooks.json` into `~/.gemini/config/hooks.json`.

### Option 3: Project Workspace Hook
1. Copy `scripts/research-flash-lite.py` to `<project-root>/.agents/scripts/research-flash-lite.py`.
2. Copy `agents/*.md` to `<project-root>/.agents/agents/`.
3. Copy `hooks.json` to `<project-root>/.agents/hooks.json`.

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
