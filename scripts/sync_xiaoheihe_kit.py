#!/usr/bin/env python3
"""Import or check a generated Xiaoheihe kit without executing its code."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher"
SOURCE_URL = "https://github.com/HSJ-BanFan/xiaoheihe-api-collect"
WHEEL_SHA256 = "2ca9af8ece4e105631e62c6c4043e1fa758c766e16031afd4e52028bc44293ff"
SOURCE_MEMBERS = {"SKILL.md", "scripts/xhh_cli.py", "scripts/xhh_publish.py",
                  "references/setup.md", "references/publishing.md", "LICENSE"}
RUNTIME_MODULES = {"__init__.py", "accounts.py", "api_catalog.json", "browse.py", "catalog.py",
                   "cli.py", "client.py", "config.py", "exceptions.py", "groups.py",
                   "interaction.py", "login.py", "payload.py", "routes.py", "secure_phone.py",
                   "signer.py", "signer_bundle.py", "signer_resources.py", "transport.py"}
DIST_INFO = "runtime/xhh_sdk-0.5.0rc4+standalone.7.dist-info/"
RUNTIME_MEMBERS = {"runtime/xhh_sdk/" + name for name in RUNTIME_MODULES} | {
    DIST_INFO + name for name in ("licenses/LICENSE", "METADATA", "WHEEL", "entry_points.txt",
                                  "top_level.txt", "RECORD")
}
HOST_PATH = re.compile(r"(?<![A-Za-z])[A-Za-z]:[/\\]|/(?:Users|home)/[^/\s]+/", re.I)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def read_kit(source: Path) -> tuple[dict, dict[str, bytes]]:
    if source.is_symlink():
        raise ValueError("Kit root must not be a symlink")
    manifest_path = source / "kit-manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("Manifest must not be a symlink")
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    expected = {"schema_version": 1, "kit_name": "xhh-publisher-kit", "kit_version": "0.1.0rc1",
                "cli_version": "0.5.0rc4+standalone.7", "wheel_sha256": WHEEL_SHA256}
    if not isinstance(manifest, dict) or any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("Unsupported kit version or original wheel")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != SOURCE_MEMBERS | RUNTIME_MEMBERS:
        raise ValueError("Missing or unexpected source/runtime members")
    for name, digest in files.items():
        path = PurePosixPath(name)
        if (name not in SOURCE_MEMBERS | RUNTIME_MEMBERS or path.is_absolute()
                or ".." in path.parts or "\\" in name or path.as_posix() != name
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Unsupported manifest member")
    found = set()
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("Kit members must not be symlinks")
        if path.is_file():
            found.add(path.relative_to(source).as_posix())
    if found != set(files) | {"kit-manifest.json"}:
        raise ValueError("Unlisted or missing kit files")
    snapshot = {"kit-manifest.json": raw}
    for name, digest in files.items():
        data = (source / name).read_bytes()
        if sha256(data) != digest:
            raise ValueError(f"Hash mismatch: {name}")
        text = data.decode("utf-8")
        if "\x00" in text or HOST_PATH.search(text):
            raise ValueError(f"Binary or host-bound member: {name}")
        snapshot[name] = data
    if HOST_PATH.search(raw.decode("utf-8")):
        raise ValueError("Host path in manifest")
    return manifest, snapshot


def source_record(manifest: dict, snapshot: dict[str, bytes], commit: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Source commit must be a full lowercase Git SHA")
    return {"source_url": SOURCE_URL, "source_commit": commit,
            "kit_version": manifest["kit_version"], "cli_version": manifest["cli_version"],
            "wheel_sha256": manifest["wheel_sha256"],
            "manifest_sha256": sha256(snapshot["kit-manifest.json"]),
            "files": {name: sha256(data) for name, data in snapshot.items()}}


def check(target: Path) -> dict[str, bytes]:
    manifest, snapshot = read_kit(target)
    record_path = target.parent / "SOURCE.json"
    if record_path.is_symlink():
        raise ValueError("Source record must not be a symlink")
    record = json.loads(record_path.read_bytes())
    if record != source_record(manifest, snapshot, record["source_commit"]):
        raise ValueError("Consumer snapshot differs from SOURCE.json")
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync")
    sync.add_argument("--from", dest="source", required=True)
    sync.add_argument("--to", default=str(TARGET))
    sync.add_argument("--source-commit", required=True)
    verify = sub.add_parser("check")
    verify.add_argument("--to", default=str(TARGET))
    args = parser.parse_args(argv)
    try:
        target = Path(args.to).absolute()
        if args.command == "check":
            check(target)
        else:
            source = Path(args.source).absolute()
            if source.resolve() == target.resolve() or source.resolve() in target.resolve().parents:
                raise ValueError("Input kit and consumer destination must be separate")
            manifest, snapshot = read_kit(source)
            record = source_record(manifest, snapshot, args.source_commit)
            previous = check(target) if target.exists() else {}
            if not target.exists() and (target.parent / "SOURCE.json").exists():
                raise ValueError("Existing SOURCE.json without a kit; restore before syncing")
            target.mkdir(parents=True, exist_ok=True)
            for name, data in snapshot.items():
                destination = target / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            for name in previous.keys() - snapshot.keys():
                stale = target / name
                if not stale.resolve().is_relative_to(target.resolve()):
                    raise ValueError("Stale member escapes destination")
                stale.unlink()
            (target.parent / "SOURCE.json").write_bytes(json_bytes(record))
            check(target)
    except (OSError, ValueError, KeyError, TypeError):
        print("Kit verification failed; no unverified input is accepted. Restore local changes before syncing.",
              file=sys.stderr)
        return 2
    print("OK: Xiaoheihe kit manifest and exact consumer snapshot verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
