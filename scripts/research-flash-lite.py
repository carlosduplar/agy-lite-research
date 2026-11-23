#!/usr/bin/env python3
"""PreToolUse hook for Google Antigravity.

Rewrites invoke_subagent calls targeting the research subagent to use
`flash_lite` (or another configured model) instead of inheriting the
parent frontier model.
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
