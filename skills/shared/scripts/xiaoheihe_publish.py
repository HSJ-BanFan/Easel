#!/usr/bin/env python3
"""Easel output and content gates around the bundled Xiaoheihe publisher kit."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import content_guard
from output_paths import validate_output_path


def kit_script() -> Path:
    relative = Path("skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_publish.py")
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
    raise ValueError("Bundled Xiaoheihe kit is missing; restore the verified snapshot")


def run_kit(script: Path, args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(script), *args], shell=False,
                          capture_output=True, text=True, encoding="utf-8", env=env)


def refuse(reason: str, *, unknown: bool = False) -> int:
    print(json.dumps({"state": "outcome_unknown" if unknown else "refused", "reason": reason}))
    return 3 if unknown else 2


def emit(result: subprocess.CompletedProcess) -> int:
    try:
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise ValueError
    except (ValueError, TypeError):
        return refuse("Kit returned no valid receipt; do not retry a submission",
                      unknown=True)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Freeze an offline plan and local images")
    plan.add_argument("spec")
    plan.add_argument("--account", required=True)
    plan.add_argument("--mode", choices=("draft", "public"), required=True)
    plan.add_argument("--out", required=True)
    show = commands.add_parser("show", help="Validate and inspect the frozen plan")
    show.add_argument("operation")
    submit = commands.add_parser("submit", help="Submit the approved plan once")
    submit.add_argument("operation")
    submit.add_argument("--approval", required=True)
    submit.add_argument("--exec", action="store_true")
    reconcile = commands.add_parser("reconcile", help="Read back without republishing")
    reconcile.add_argument("operation")
    args = parser.parse_args(argv)

    if args.command == "submit" and not args.exec:
        return refuse("Submission requires explicit user approval and --exec")
    dispatched = False
    try:
        operation = validate_output_path(args.out if args.command == "plan" else args.operation)
        script = kit_script()
        if args.command == "plan":
            return emit(run_kit(script, ["plan", str(Path(args.spec).expanduser().resolve()),
                                         "--account", args.account, "--mode", args.mode,
                                         "--out", str(operation)]))
        if args.command == "submit":
            shown = run_kit(script, ["show", str(operation)])
            if shown.returncode:
                return refuse("Frozen plan validation failed; submission was not started")
            frozen = json.loads(shown.stdout)
            if not isinstance(frozen, dict) or frozen.get("approval_sha256") != args.approval:
                return refuse("Approval does not match the frozen plan")
            spec = frozen["spec"]
            parts = [spec.get("title", ""), spec.get("content", ""), *spec.get("hashtags", [])]
            if spec.get("content_format") == "html":
                parts.append(html.unescape(re.sub(r"<[^>]+>", "", spec["content"])))
                markup = re.sub(r"<br\s*/?>", "\n", spec["content"], flags=re.I)
                markup = re.sub(r"</(?:p|h[1-6]|li|blockquote|div)>", "\n", markup, flags=re.I)
                visible = html.unescape(re.sub(r"<[^>]+>", "", markup))
                parts.extend([visible, visible.replace("\n", " ").strip()[:100]])
            content_guard.guard_or_die(parts, exec_mode=True, label="Xiaoheihe outgoing content")
            dispatched = True
            return emit(run_kit(script, ["submit", str(operation), "--approval", args.approval,
                                         "--confirm"]))
        return emit(run_kit(script, [args.command, str(operation)]))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return refuse("Unable to validate or run the kit; inspect the operation before continuing",
                      unknown=dispatched)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
