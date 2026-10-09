#!/usr/bin/env python3
"""Import a user-supplied APK through the bundled, pinned Xiaoheihe setup kit."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def kit_script() -> Path:
    relative = Path("skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_setup.py")
    configured = os.environ.get("EASEL_ROOT", "").strip()
    if configured:
        candidates = [Path(configured).expanduser() / "skills/openclaw" / relative]
    else:
        shared_parent = Path(__file__).resolve().parents[2]
        candidates = [shared_parent / "openclaw" / relative,
                      shared_parent / "skills" / relative]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Bundled setup kit is missing")


def refuse(reason: str) -> int:
    print(json.dumps({"state": "refused", "reason": reason}))
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", required=True, help="User-supplied supported APK; never uploaded")
    parser.add_argument("--confirm", action="store_true", help="Authorize local import and self-test")
    parser.add_argument("--account", help="Bind only this existing alias after self-test")
    parser.add_argument("--data-dir", help="Use the same private account store as the original CLI")
    parser.add_argument("--java", help="Explicit Java executable")
    parser.add_argument("--install-java", action="store_true", help="Allow a pinned private JRE download")
    parser.add_argument("--offline", action="store_true", help="Require verified cached artifacts")
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser.parse_args(arguments)
    try:
        script = kit_script()
    except OSError:
        return refuse("kit_missing")
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    try:
        # The canonical runner owns the bounded download and Java operations.
        result = subprocess.run([sys.executable, str(script), *arguments], shell=False,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt):
        return refuse("setup_interrupted")
    try:
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict) or payload.get("state") not in {"ready", "refused"}:
            raise ValueError
        if (payload["state"] == "ready") != (result.returncode == 0):
            raise ValueError
        if payload["state"] == "ready":
            selftest = payload.get("selftest")
            if (not isinstance(selftest, dict) or selftest.get("executed") is not True
                    or selftest.get("matched") is not True):
                raise ValueError
    except (ValueError, TypeError):
        return refuse("setup_result_invalid")
    sys.stderr.write(result.stderr)
    print(json.dumps(payload, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
