"""The Easel entry delegates setup without owning credentials or import policy."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/shared/scripts/xiaoheihe_setup.py"
RELATIVE = Path("skill-xiaoheihe-publisher/vendor/xiaoheihe-publisher/scripts/xhh_setup.py")


def load_adapter():
    assert SCRIPT.is_file(), "Missing one-command Easel APK setup entry"
    spec = importlib.util.spec_from_file_location("easel_xhh_setup", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_script(path):
    path.parent.mkdir(parents=True)
    path.write_text(
        "import json, sys\n"
        "print('setup progress', file=sys.stderr)\n"
        "print(json.dumps({'state': 'refused', 'reason': 'fixture', 'argv': sys.argv[1:]}))\n"
        "sys.exit(2)\n", encoding="utf-8")


def test_setup_passes_explicit_arguments_and_child_refusal(tmp_path, monkeypatch, capsys):
    adapter = load_adapter()
    monkeypatch.setenv("EASEL_ROOT", str(tmp_path))
    fixture_script(tmp_path / "skills/openclaw" / RELATIVE)
    args = ["--apk", "input with space.apk", "--account", "chosen-alias", "--java",
            "runtime path/java.exe", "--data-dir", "private store", "--offline",
            "--install-java", "--confirm"]
    run = adapter.subprocess.run
    invocations = []

    def capture(argv, **kwargs):
        invocations.append((argv, kwargs))
        return run(argv, **kwargs)

    monkeypatch.setattr(adapter.subprocess, "run", capture)
    assert adapter.main(args) == 2
    output = capsys.readouterr()
    assert json.loads(output.out) == {"state": "refused", "reason": "fixture", "argv": args}
    assert output.err == "setup progress\n"
    argv, kwargs = invocations[0]
    assert argv[0] == sys.executable and argv[2:] == args
    assert kwargs["shell"] is False
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    if os.name == "nt":
        assert kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW


def test_setup_help_needs_no_vendor_or_resources(tmp_path, monkeypatch, capsys):
    adapter = load_adapter()
    monkeypatch.setenv("EASEL_ROOT", str(tmp_path))
    with pytest.raises(SystemExit) as exit_info:
        adapter.main(["--help"])
    assert exit_info.value.code == 0
    assert "--apk" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_setup_never_supplies_confirmation_or_default_account(tmp_path, monkeypatch, capsys):
    adapter = load_adapter()
    monkeypatch.setenv("EASEL_ROOT", str(tmp_path))
    fixture_script(tmp_path / "skills/openclaw" / RELATIVE)
    assert adapter.main(["--apk", "input.apk"]) == 2
    assert json.loads(capsys.readouterr().out)["argv"] == ["--apk", "input.apk"]


def test_missing_configured_kit_does_not_fall_back(monkeypatch, tmp_path, capsys):
    adapter = load_adapter()
    monkeypatch.setenv("EASEL_ROOT", str(tmp_path))
    assert adapter.main(["--apk", "input.apk", "--confirm"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "kit_missing"


def test_copied_workspace_resolves_kit_without_checkout(tmp_path):
    assert SCRIPT.is_file(), "Missing one-command Easel APK setup entry"
    copied = tmp_path / "workspace/shared/scripts/xiaoheihe_setup.py"
    copied.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, copied)
    fixture_script(tmp_path / "workspace/skills" / RELATIVE)
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("EASEL_ROOT", None)
    result = subprocess.run([sys.executable, str(copied), "--apk", "some input.apk"],
                            env=env, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2
    assert json.loads(result.stdout)["argv"] == ["--apk", "some input.apk"]


def test_invalid_child_output_cannot_claim_ready(tmp_path, monkeypatch, capsys):
    adapter = load_adapter()
    monkeypatch.setenv("EASEL_ROOT", str(tmp_path))
    script = tmp_path / "skills/openclaw" / RELATIVE
    script.parent.mkdir(parents=True)
    script.write_text("print('not JSON')\n", encoding="utf-8")
    assert adapter.main(["--apk", "input.apk", "--confirm"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "setup_result_invalid"


def test_setup_timeout_is_a_refusal(monkeypatch, tmp_path, capsys):
    adapter = load_adapter()
    monkeypatch.setenv("EASEL_ROOT", str(tmp_path))
    fixture_script(tmp_path / "skills/openclaw" / RELATIVE)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 60)

    monkeypatch.setattr(adapter.subprocess, "run", timeout)
    assert adapter.main(["--apk", "input.apk", "--confirm"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "setup_interrupted"


def test_non_utf8_child_output_is_a_sanitized_refusal(tmp_path, monkeypatch, capsys):
    adapter = load_adapter()
    monkeypatch.setenv("EASEL_ROOT", str(tmp_path))
    script = tmp_path / "skills/openclaw" / RELATIVE
    script.parent.mkdir(parents=True)
    script.write_text("import sys\nsys.stdout.buffer.write(b'\\xff')\n", encoding="utf-8")
    assert adapter.main(["--apk", "input.apk", "--confirm"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "setup_result_invalid"


@pytest.mark.parametrize("payload,code", [
    ({"state": "ready"}, 0),
    ({"state": "ready", "selftest": {"executed": True, "matched": False}}, 0),
    ({"state": "refused", "reason": "fixture"}, 0),
    ({"state": "ready", "selftest": {"executed": True, "matched": True}}, 2),
])
def test_inconsistent_or_untested_success_is_refused(payload, code, tmp_path, monkeypatch, capsys):
    adapter = load_adapter()
    monkeypatch.setenv("EASEL_ROOT", str(tmp_path))
    script = tmp_path / "skills/openclaw" / RELATIVE
    script.parent.mkdir(parents=True)
    script.write_text(f"import sys\nprint({json.dumps(payload)!r})\nsys.exit({code})\n", encoding="utf-8")
    assert adapter.main(["--apk", "input.apk", "--confirm"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "setup_result_invalid"


@pytest.fixture
def portable_kit(tmp_path):
    workspace = tmp_path / "copied \u5de5\u4f5c\u533a workspace"
    adapter = workspace / "shared/scripts/xiaoheihe_setup.py"
    adapter.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, adapter)
    source = ROOT / "skills/openclaw/skill-xiaoheihe-publisher/vendor"
    vendor = workspace / "skills/skill-xiaoheihe-publisher/vendor"
    shutil.copytree(source, vendor)
    kit = vendor / "xiaoheihe-publisher"
    assert (kit / "scripts/xhh_setup.py").is_file(), "Snapshot must include the real setup kit"
    private = tmp_path / "isolated \u7528\u6237 home"
    private.mkdir()
    accounts = private / "accounts"
    accounts.mkdir()
    (accounts / "sentinel").write_text("never change existing account data", encoding="utf-8")
    apk = tmp_path / "unsupported \u8f93\u5165 input.apk"
    apk.write_bytes(b"This is deliberately not a supported APK.")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("XHH_", "EASEL_"))}
    env.update(HOME=str(private), USERPROFILE=str(private),
               XHH_SETUP_HOME=str(private / "cache"), XHH_BUNDLE_HOME=str(private / "bundles"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    return adapter, kit, private, accounts, apk, env


def private_snapshot(private):
    return {str(path.relative_to(private)): path.read_bytes() if path.is_file() else None
            for path in private.rglob("*")}


@pytest.mark.parametrize("mode,reason", [
    ("help", None),
    ("no-confirm", "confirmation_required"),
    ("wrong-apk", "unsupported_apk"),
    ("tampered-kit", "kit_integrity_failed"),
])
def test_real_copied_setup_refuses_before_side_effects(portable_kit, mode, reason):
    adapter, kit, private, accounts, apk, env = portable_kit
    args = ["--apk", str(apk), "--data-dir", str(accounts), "--install-java"]
    if mode == "help":
        args = ["--help"]
    elif mode != "no-confirm":
        args.append("--confirm")
    if mode == "tampered-kit":
        (kit / "references/signer-release.json").write_text("{}\n", encoding="utf-8")
    before = private_snapshot(private)
    result = subprocess.run([sys.executable, str(adapter), *args], env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert result.returncode == (0 if mode == "help" else 2), result.stderr
    if mode == "help":
        assert "--apk" in result.stdout and "--install-java" in result.stdout
    else:
        payload = json.loads(result.stdout)
        assert payload["state"] == "refused"
        assert payload["reason"] == reason
        assert payload["account_binding"] == {"requested": False, "bound": False, "changed": False}
    assert private_snapshot(private) == before
    assert not list(kit.rglob("__pycache__"))


def test_bundled_release_is_text_only_with_original_runtime():
    vendor = ROOT / "skills/openclaw/skill-xiaoheihe-publisher/vendor"
    kit = vendor / "xiaoheihe-publisher"
    manifest = json.loads((kit / "kit-manifest.json").read_bytes())
    source = json.loads((vendor / "SOURCE.json").read_bytes())
    assert manifest["kit_version"] == source["kit_version"] == "0.2.0rc1"
    assert manifest["wheel_sha256"] == "2ca9af8ece4e105631e62c6c4043e1fa758c766e16031afd4e52028bc44293ff"
    files = [path for path in kit.rglob("*") if path.is_file()]
    assert len(files) == 35
    assert sum(name.startswith("runtime/") for name in manifest["files"]) == 25
    for path in files:
        assert path.suffix.lower() not in {".jar", ".apk", ".so", ".exe", ".dll", ".zip"}
        assert "\x00" not in path.read_text(encoding="utf-8")
