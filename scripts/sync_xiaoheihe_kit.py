#!/usr/bin/env python3
"""Import or check a generated Xiaoheihe kit without executing its code."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "skills/openclaw/skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher"
SOURCE_URL = "https://github.com/HSJ-BanFan/xiaoheihe-api-collect"
WHEEL_SHA256 = "2ca9af8ece4e105631e62c6c4043e1fa758c766e16031afd4e52028bc44293ff"
SOURCE_MEMBERS = {"SKILL.md", "scripts/xhh_cli.py", "scripts/xhh_publish.py",
                  "references/setup.md", "references/publishing.md", "LICENSE"}
VERSION_SOURCES = {
    "0.1.0rc1": SOURCE_MEMBERS,
    "0.2.0rc1": SOURCE_MEMBERS | {"scripts/xhh_setup.py", "scripts/setup_runtime.py",
                                 "references/signer-release.json"},
}
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


def is_link(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0)
                                     & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def read_kit(source: Path) -> tuple[dict, dict[str, bytes]]:
    if is_link(source):
        raise ValueError("Kit root must not be a symlink")
    manifest_path = source / "kit-manifest.json"
    if is_link(manifest_path):
        raise ValueError("Manifest must not be a symlink")
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    expected = {"schema_version": 1, "kit_name": "xhh-publisher-kit",
                "cli_version": "0.5.0rc4+standalone.7", "wheel_sha256": WHEEL_SHA256}
    if not isinstance(manifest, dict) or any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("Unsupported kit version or original wheel")
    version = manifest.get("kit_version")
    if not isinstance(version, str) or version not in VERSION_SOURCES:
        raise ValueError("Unsupported kit version")
    members = VERSION_SOURCES[version] | RUNTIME_MEMBERS
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != members:
        raise ValueError("Missing or unexpected source/runtime members")
    for name, digest in files.items():
        path = PurePosixPath(name)
        if (name not in members or path.is_absolute()
                or ".." in path.parts or "\\" in name or path.as_posix() != name
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Unsupported manifest member")
    found = set()
    directories = {parent.as_posix() for name in files for parent in PurePosixPath(name).parents
                   if parent != PurePosixPath(".")}
    for path in source.rglob("*"):
        if is_link(path):
            raise ValueError("Kit members must not be symlinks")
        if path.is_file():
            found.add(path.relative_to(source).as_posix())
        elif not path.is_dir() or path.relative_to(source).as_posix() not in directories:
            raise ValueError("Unlisted kit directory or special entry")
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
    if is_link(record_path):
        raise ValueError("Source record must not be a symlink")
    record = json.loads(record_path.read_bytes())
    if record != source_record(manifest, snapshot, record["source_commit"]):
        raise ValueError("Consumer snapshot differs from SOURCE.json")
    return snapshot


def checked_vendor(vendor: Path, kit_name: str) -> dict[str, bytes]:
    entries = {p.name for p in vendor.iterdir()}
    if is_link(vendor) or entries - {kit_name, "SOURCE.json", ".gitattributes"}:
        raise ValueError("Vendor directory has unreviewed entries")
    snapshot = check(vendor / kit_name)
    files = {**snapshot, "SOURCE.json": (vendor / "SOURCE.json").read_bytes()}
    if ".gitattributes" in entries:
        attributes = vendor / ".gitattributes"
        if is_link(attributes):
            raise ValueError("Git attributes must not be a link")
        data = attributes.read_bytes()
        if data.replace(b"\r\n", b"\n") != b"xiaoheihe-publisher/** -text whitespace=cr-at-eol,-blank-at-eof\n":
            raise ValueError("Git attributes have unreviewed changes")
        files[".gitattributes"] = data
    return files


def remove_owned_tree(path: Path, parent: Path, prefix: str) -> None:
    if path.resolve().parent != parent.resolve() or not path.name.startswith(prefix) or is_link(path):
        raise ValueError("Cleanup target escapes transaction directory")
    if any(is_link(member) for member in path.rglob("*")):
        raise ValueError("Cleanup target contains a link")
    shutil.rmtree(path)


@contextmanager
def sync_lock(path: Path):
    # OS locks release on process exit, including an interrupted directory swap.
    if path.exists() and is_link(path):
        raise ValueError("Transaction lock must not be a link")
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def install_snapshot(target: Path, manifest: dict, snapshot: dict[str, bytes], record: dict) -> None:
    if target != target.resolve() or not target.name or target.name in {".", ".."}:
        raise ValueError("Consumer target must be a canonical directory path")
    vendor = target.parent
    parent = vendor.parent
    prefix = f".{vendor.name}.xhh-"
    backup = parent / (prefix + "backup")
    parent.mkdir(parents=True, exist_ok=True)
    with sync_lock(parent / (prefix + "lock")):
        if backup.exists():
            checked_vendor(backup, target.name)
            if not vendor.exists():
                backup.rename(vendor)
            else:
                checked_vendor(vendor, target.name)
                remove_owned_tree(backup, parent, prefix)
        previous = checked_vendor(vendor, target.name) if vendor.exists() else None
        attributes = {".gitattributes": previous[".gitattributes"]} if previous and ".gitattributes" in previous else {}
        if previous:
            if any(previous[name] != snapshot[name] for name in RUNTIME_MEMBERS):
                raise ValueError("Original wheel runtime must remain byte-identical")
            old_version = json.loads(previous["kit-manifest.json"])["kit_version"]
            if list(VERSION_SOURCES).index(old_version) > list(VERSION_SOURCES).index(manifest["kit_version"]):
                raise ValueError("Kit downgrades are not supported")
            if previous == {**snapshot, "SOURCE.json": json_bytes(record), **attributes}:
                return
        stage = Path(tempfile.mkdtemp(prefix=prefix + "stage-", dir=parent))
        try:
            for name, data in snapshot.items():
                destination = stage / target.name / name
                if not destination.resolve().is_relative_to(stage.resolve() / target.name):
                    raise ValueError("Staged member escapes the kit directory")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            (stage / "SOURCE.json").write_bytes(json_bytes(record))
            for name, data in attributes.items():
                (stage / name).write_bytes(data)
            checked_vendor(stage, target.name)
            if previous is not None:
                if checked_vendor(vendor, target.name) != previous:
                    raise ValueError("Consumer changed while staging")
                vendor.rename(backup)
            try:
                stage.rename(vendor)
            except BaseException:
                if backup.exists() and not vendor.exists():
                    backup.rename(vendor)
                raise
            checked_vendor(vendor, target.name)
            if backup.exists():
                checked_vendor(backup, target.name)
                remove_owned_tree(backup, parent, prefix)
        finally:
            if stage.exists():
                remove_owned_tree(stage, parent, prefix)


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
        if not args.to.strip() or target != target.resolve() or not target.name:
            raise ValueError("Consumer target must be a canonical directory path")
        if args.command == "check":
            check(target)
        else:
            source = Path(args.source).absolute()
            vendor = target.parent
            if (source.resolve() == vendor.resolve() or source.resolve() in vendor.resolve().parents
                    or vendor.resolve() in source.resolve().parents or vendor.resolve() != vendor):
                raise ValueError("Input kit and consumer destination must be separate")
            manifest, snapshot = read_kit(source)
            record = source_record(manifest, snapshot, args.source_commit)
            install_snapshot(target, manifest, snapshot, record)
    except (OSError, ValueError, KeyError, TypeError):
        print("Kit verification failed; no unverified input is accepted. Restore local changes before syncing.",
              file=sys.stderr)
        return 2
    print("OK: Xiaoheihe kit manifest and exact consumer snapshot verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
