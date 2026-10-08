"""The consumer snapshot importer must reject tampered or host-bound kits."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/sync_xiaoheihe_kit.py"
WHEEL_SHA256 = "2ca9af8ece4e105631e62c6c4043e1fa758c766e16031afd4e52028bc44293ff"


def importer():
    assert SCRIPT.is_file(), "Missing verified kit importer"
    spec = importlib.util.spec_from_file_location("sync_xiaoheihe_kit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def kit(tmp_path):
    source = tmp_path / "input-kit"
    members = {
        "SKILL.md": b"# Synthetic kit\n",
        "scripts/xhh_cli.py": b"print('synthetic cli')\n",
        "scripts/xhh_publish.py": b"print('synthetic publisher')\n",
        "references/setup.md": b"# Setup\n",
        "references/publishing.md": b"# Publishing\n",
        "LICENSE": b"Synthetic license fixture\n",
        "runtime/xhh_sdk/__init__.py": b"# Synthetic runtime\n",
    }
    for name in ("accounts.py", "api_catalog.json", "browse.py", "catalog.py", "cli.py", "client.py",
                 "config.py", "exceptions.py", "groups.py", "interaction.py", "login.py", "payload.py",
                 "routes.py", "secure_phone.py", "signer.py", "signer_bundle.py", "signer_resources.py", "transport.py"):
        members["runtime/xhh_sdk/" + name] = b"# Synthetic fixture\n"
    for name in ("licenses/LICENSE", "METADATA", "WHEEL", "entry_points.txt", "top_level.txt", "RECORD"):
        members["runtime/xhh_sdk-0.5.0rc4+standalone.7.dist-info/" + name] = b"Synthetic metadata\n"
    for name, data in members.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = {"schema_version": 1, "kit_name": "xhh-publisher-kit", "kit_version": "0.1.0rc1",
                "cli_version": "0.5.0rc4+standalone.7", "wheel_sha256": WHEEL_SHA256,
                "files": {name: digest(data) for name, data in members.items()}}
    (source / "kit-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return source


def test_import_is_byte_exact_and_check_catches_drift(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    assert module.main(["sync", "--from", str(kit), "--to", str(target),
                        "--source-commit", "1" * 40]) == 0
    for source in kit.rglob("*"):
        if source.is_file():
            assert (target / source.relative_to(kit)).read_bytes() == source.read_bytes()
    record = json.loads((target.parent / "SOURCE.json").read_text())
    assert record["source_commit"] == "1" * 40
    assert record["manifest_sha256"] == digest((kit / "kit-manifest.json").read_bytes())
    assert str(tmp_path) not in json.dumps(record)
    assert module.main(["check", "--to", str(target)]) == 0
    (target / "SKILL.md").write_text("changed")
    assert module.main(["check", "--to", str(target)]) == 2


@pytest.mark.parametrize("mutation", ["hash", "unlisted", "binary", "host", "host-drive", "traversal", "version"])
def test_bad_source_is_refused_before_copy(kit, tmp_path, mutation):
    module = importer()
    manifest_path = kit / "kit-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if mutation == "hash":
        (kit / "SKILL.md").write_text("tampered")
    elif mutation in ("unlisted", "binary"):
        path = kit / "runtime/xhh_sdk/proprietary.dll"
        path.write_bytes(b"MZ\x00\x01")
        if mutation == "binary":
            manifest["files"][path.relative_to(kit).as_posix()] = digest(path.read_bytes())
    elif mutation in ("host", "host-drive"):
        path = kit / "references/setup.md"
        path.write_text("Run C:/Users/somebody/private/tool.py" if mutation == "host"
                        else "Run Z:/private/tool.py", encoding="utf-8")
        manifest["files"]["references/setup.md"] = digest(path.read_bytes())
    elif mutation == "traversal":
        manifest["files"]["../escaped.py"] = "a" * 64
    else:
        manifest["cli_version"] = "unreviewed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    target = tmp_path / "vendor/xiaoheihe-publisher"
    assert module.main(["sync", "--from", str(kit), "--to", str(target),
                        "--source-commit", "1" * 40]) == 2
    assert not target.exists()


def test_refresh_refuses_to_overwrite_unreviewed_local_changes(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    snapshot = (target.parent / "SOURCE.json").read_bytes()
    assert module.main(args) == 0
    assert (target.parent / "SOURCE.json").read_bytes() == snapshot
    (target / "SKILL.md").write_text("local edits")
    assert module.main(args) == 2
    assert (target / "SKILL.md").read_text() == "local edits"


def test_manifest_cannot_drop_required_runtime_member(kit, tmp_path):
    module = importer()
    path = kit / "runtime/xhh_sdk/cli.py"
    path.unlink()
    manifest_path = kit / "kit-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    del manifest["files"]["runtime/xhh_sdk/cli.py"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    target = tmp_path / "vendor/xiaoheihe-publisher"
    assert module.main(["sync", "--from", str(kit), "--to", str(target),
                        "--source-commit", "1" * 40]) == 2
    assert not target.exists()
