"""The consumer snapshot importer must reject tampered or host-bound kits."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

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


def upgrade_kit(kit):
    manifest_path = kit / "kit-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["kit_version"] = "0.2.0rc1"
    for name in ("scripts/xhh_setup.py", "scripts/setup_runtime.py", "references/signer-release.json"):
        data = b"{}\n" if name.endswith(".json") else b"# Synthetic setup fixture\n"
        (kit / name).write_bytes(data)
        manifest["files"][name] = digest(data)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_upgrade_validates_old_snapshot_then_installs_new_exact_members(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    upgrade_kit(kit)
    assert module.main(args) == 0
    assert module.main(["check", "--to", str(target)]) == 0
    assert json.loads((target.parent / "SOURCE.json").read_bytes())["kit_version"] == "0.2.0rc1"
    assert (target / "scripts/xhh_setup.py").read_bytes() == (kit / "scripts/xhh_setup.py").read_bytes()


def test_upgrade_rejects_old_version_with_new_members(kit, tmp_path):
    module = importer()
    upgrade_kit(kit)
    manifest_path = kit / "kit-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["kit_version"] = "0.1.0rc1"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    target = tmp_path / "vendor/xiaoheihe-publisher"
    assert module.main(["sync", "--from", str(kit), "--to", str(target),
                        "--source-commit", "1" * 40]) == 2
    assert not target.exists()


def test_failed_upgrade_restores_old_tree_and_source_record(kit, tmp_path, monkeypatch):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    before = {p.relative_to(target.parent): p.read_bytes() for p in target.parent.rglob("*") if p.is_file()}
    upgrade_kit(kit)
    rename = Path.rename

    def fail_publish(path, destination):
        if Path(destination) == target.parent and path != target.parent.with_name(".vendor.xhh-backup"):
            raise OSError("injected stage publish failure")
        return rename(path, destination)

    monkeypatch.setattr(Path, "rename", fail_publish)
    assert module.main(args) == 2
    assert {p.relative_to(target.parent): p.read_bytes() for p in target.parent.rglob("*") if p.is_file()} == before
    assert module.main(["check", "--to", str(target)]) == 0


def test_sync_recovers_verified_backup_after_interrupted_rename(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    backup = target.parent.with_name(".vendor.xhh-backup")
    target.parent.rename(backup)
    upgrade_kit(kit)
    assert module.main(args) == 0
    assert not backup.exists()
    assert module.main(["check", "--to", str(target)]) == 0


def test_sync_preserves_unrelated_vendor_files(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    unrelated = target.parent / "user-notes.txt"
    unrelated.write_text("keep these notes", encoding="utf-8")
    upgrade_kit(kit)
    assert module.main(args) == 2
    assert unrelated.read_text() == "keep these notes"
    assert json.loads((target / "kit-manifest.json").read_bytes())["kit_version"] == "0.1.0rc1"


def test_sync_refuses_downgrade(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    old = tmp_path / "old-kit"
    shutil.copytree(kit, old)
    upgrade_kit(kit)
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    assert module.main(["sync", "--from", str(old), "--to", str(target),
                        "--source-commit", "2" * 40]) == 2
    assert json.loads((target / "kit-manifest.json").read_bytes())["kit_version"] == "0.2.0rc1"


def test_interrupted_backup_with_drift_is_not_restored_or_removed(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    backup = target.parent.with_name(".vendor.xhh-backup")
    target.parent.rename(backup)
    edited = backup / target.name / "SKILL.md"
    edited.write_text("local recovery notes", encoding="utf-8")
    assert module.main(args) == 2
    assert edited.read_text() == "local recovery notes"
    assert not target.parent.exists()


def test_source_cannot_be_nested_in_vendor_transaction(kit, tmp_path):
    module = importer()
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    nested = vendor / "source-kit"
    shutil.copytree(kit, nested)
    target = vendor / "xiaoheihe-publisher"
    assert module.main(["sync", "--from", str(nested), "--to", str(target),
                        "--source-commit", "1" * 40]) == 2
    assert (nested / "kit-manifest.json").is_file()
    assert not target.exists()


def test_staging_write_failure_preserves_existing_snapshot(kit, tmp_path, monkeypatch):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    old = module.check(target)
    old_record = (target.parent / "SOURCE.json").read_bytes()
    upgrade_kit(kit)
    write = Path.write_bytes

    def fail_write(path, data):
        if path.name == "xhh_setup.py" and any(".vendor.xhh-stage-" in part for part in path.parts):
            raise OSError("injected disk write failure")
        return write(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    assert module.main(args) == 2
    assert module.check(target) == old
    assert (target.parent / "SOURCE.json").read_bytes() == old_record


def test_another_process_holding_transaction_lock_prevents_sync(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    lock = tmp_path / ".vendor.xhh-lock"
    lock.write_bytes(b"0")
    with lock.open("r+b") as stream:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run([sys.executable, str(SCRIPT), "sync", "--from", str(kit),
                                 "--to", str(target), "--source-commit", "1" * 40],
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 2
    assert not target.exists()
    assert module.main(["sync", "--from", str(kit), "--to", str(target),
                        "--source-commit", "1" * 40]) == 0


def test_successful_swap_leftover_backup_is_verified_and_cleaned(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    backup = tmp_path / ".vendor.xhh-backup"
    shutil.copytree(target.parent, backup)
    upgrade_kit(kit)
    assert module.main(args) == 0
    assert not backup.exists()
    assert module.main(["check", "--to", str(target)]) == 0


def test_unlisted_empty_directory_is_local_drift_not_disposable(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    notes = target / "private-notes"
    notes.mkdir()
    upgrade_kit(kit)
    assert module.main(args) == 2
    assert notes.is_dir()
    assert json.loads((target / "kit-manifest.json").read_bytes())["kit_version"] == "0.1.0rc1"


def test_upgrade_cannot_change_the_original_runtime_bytes(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    original = (target / "runtime/xhh_sdk/cli.py").read_bytes()
    upgrade_kit(kit)
    changed = kit / "runtime/xhh_sdk/cli.py"
    changed.write_bytes(b"# A different runtime, despite the same wheel declaration\n")
    manifest_path = kit / "kit-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["files"]["runtime/xhh_sdk/cli.py"] = digest(changed.read_bytes())
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert module.main(args) == 2
    assert (target / "runtime/xhh_sdk/cli.py").read_bytes() == original


def test_upgrade_preserves_repo_gitattributes_bytes(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    attributes = target.parent / ".gitattributes"
    content = (ROOT / "skills/openclaw/skill-xiaoheihe-publisher/vendor/.gitattributes").read_bytes()
    attributes.write_bytes(content)
    upgrade_kit(kit)
    assert module.main(args) == 0
    assert attributes.read_bytes() == content
    assert module.main(["check", "--to", str(target)]) == 0


def test_upgrade_refuses_modified_attributes_without_losing_them(kit, tmp_path):
    module = importer()
    target = tmp_path / "vendor/xiaoheihe-publisher"
    args = ["sync", "--from", str(kit), "--to", str(target), "--source-commit", "1" * 40]
    assert module.main(args) == 0
    attributes = target.parent / ".gitattributes"
    attributes.write_text("* text=auto\n", encoding="utf-8")
    upgrade_kit(kit)
    assert module.main(args) == 2
    assert attributes.read_text() == "* text=auto\n"
    assert json.loads((target / "kit-manifest.json").read_bytes())["kit_version"] == "0.1.0rc1"


def test_terminal_parent_path_is_refused_before_any_writes(kit, tmp_path):
    module = importer()
    protected = tmp_path / "protected"
    protected.mkdir()
    sentinel = protected / "SOURCE.json"
    sentinel.write_bytes(b"existing unrelated source data")
    target = protected / "new-vendor" / ".."
    before = {str(p.relative_to(protected)): p.read_bytes() for p in protected.rglob("*") if p.is_file()}
    assert module.main(["sync", "--from", str(kit), "--to", str(target),
                        "--source-commit", "1" * 40]) == 2
    assert {str(p.relative_to(protected)): p.read_bytes() for p in protected.rglob("*") if p.is_file()} == before
    assert list(protected.iterdir()) == [sentinel]
