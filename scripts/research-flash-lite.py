#!/usr/bin/env python3
"""PreToolUse hook for Google Antigravity.

Rewrites invoke_subagent calls targeting the research subagent to use
`flash_lite` (or another configured model) instead of inheriting the
parent frontier model.

Handles both the flat shape (`args.TypeName` / `args.Model`) and the
batched shape (`args.Subagents`, a list or JSON-encoded list of per-agent
specs each carrying its own `TypeName` / `Model`).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

VALID_MODELS = ("flash_lite", "flash", "pro", "inherit")
INHERIT_VALUES = (None, "", "inherit")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite Antigravity invoke_subagent calls to a target model."
    )
    parser.add_argument(
        "model",
        nargs="?",
        default="flash_lite",
        help=f"Target model ({', '.join(VALID_MODELS)}). Defaults to 'flash_lite'.",
    )
    parser.add_argument(
        "--agent",
        default="research",
        help="Subagent TypeName to target. Defaults to 'research'.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rewrite even when an explicit non-inherit model was requested.",
    )
    args = parser.parse_args(argv)

    if args.model not in VALID_MODELS:
        print(
            f"Warning: invalid model {args.model!r}; falling back to 'flash_lite'.",
            file=sys.stderr,
        )
        args.model = "flash_lite"

    return args


def _model_of(entry: dict[str, Any]) -> Any:
    """Return the model value of a subagent entry (capitalized or not)."""
    if "Model" in entry:
        return entry["Model"]
    return entry.get("model")


def _typename_of(entry: dict[str, Any]) -> Any:
    """Return the type name of a subagent entry (capitalized or not)."""
    if "TypeName" in entry:
        return entry["TypeName"]
    return entry.get("typename")


def _rewrite_entries(
    entries: list[Any],
    target_model: str,
    target_agent: str,
    force: bool,
) -> tuple[list[Any], bool]:
    """Rewrite matching entries in place-copy; return (entries, changed)."""
    changed = False
    rewritten: list[Any] = []
    for entry in entries:
        if not isinstance(entry, dict):
            rewritten.append(entry)
            continue
        model = _model_of(entry)
        needs_rewrite = model != target_model and (
            force or model in INHERIT_VALUES
        )
        if _typename_of(entry) == target_agent and needs_rewrite:
            entry = dict(entry)
            if "Model" in entry or "model" not in entry:
                entry["Model"] = target_model
            else:
                entry["model"] = target_model
            changed = True
        rewritten.append(entry)
    return rewritten, changed


def _batched_overwrite(
    tool_args: dict[str, Any],
    target_model: str,
    target_agent: str,
    force: bool,
) -> dict[str, Any] | None:
    """Handle a batched `Subagents: [...]` dispatch.

    Returns the hook response when the args carry a batched payload
    (rewritten or not), or None when no batched shape is present.
    """
    key = (
        "Subagents"
        if "Subagents" in tool_args
        else ("subagents" if "subagents" in tool_args else None)
    )
    if key is None:
        return None

    raw = tool_args[key]
    was_string = isinstance(raw, str)
    entries: Any = raw
    if was_string:
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError:
            return {"decision": "allow"}
    if not isinstance(entries, list):
        return {"decision": "allow"}

    rewritten, changed = _rewrite_entries(entries, target_model, target_agent, force)
    if not changed:
        return {"decision": "allow"}
    return {
        "decision": "allow",
        "overwrite": {key: json.dumps(rewritten) if was_string else rewritten},
    }


def process_payload(
    raw_input: str,
    target_model: str = "flash_lite",
    target_agent: str = "research",
    force: bool = False,
) -> dict[str, Any]:
    try:
        payload = json.loads(raw_input or "{}")
    except json.JSONDecodeError:
        return {"decision": "allow"}

    if not isinstance(payload, dict):
        return {"decision": "allow"}

    tool_call = payload.get("toolCall")
    if not isinstance(tool_call, dict):
        return {"decision": "allow"}

    tool_args = tool_call.get("args")
    if not isinstance(tool_args, dict):
        return {"decision": "allow"}

    batched = _batched_overwrite(tool_args, target_model, target_agent, force)
    if batched is not None:
        return batched

    current_model = tool_args.get("Model")
    is_target_agent = tool_args.get("TypeName") == target_agent
    needs_rewrite = current_model != target_model and (
        force or current_model in INHERIT_VALUES
    )

    if is_target_agent and needs_rewrite:
        return {
            "decision": "allow",
            "overwrite": {"Model": target_model},
        }

    return {"decision": "allow"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    raw_input = sys.stdin.read()
    response = process_payload(
        raw_input=raw_input,
        target_model=args.model,
        target_agent=args.agent,
        force=args.force,
    )
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
