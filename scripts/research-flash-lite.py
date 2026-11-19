#!/usr/bin/env python3
import json
import sys


VALID_MODELS = {"flash_lite", "flash", "pro", "inherit"}


def main() -> None:
    target_model = (
        sys.argv[1]
        if len(sys.argv) > 1 and sys.argv[1] in VALID_MODELS
        else "flash_lite"
    )
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}

    args = (payload.get("toolCall") or {}).get("args") or {}
    if args.get("TypeName") == "research" and args.get("Model") != target_model:
        print(json.dumps({"decision": "allow", "overwrite": {"Model": target_model}}))
    else:
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
