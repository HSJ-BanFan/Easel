from __future__ import annotations

import importlib.util
import base64
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "skills/shared/scripts"
ADAPTER = SHARED / "xiaoheihe_publish.py"
SKILL = "skill-xiaoheihe-publisher"
DIGEST = "a" * 64


def load_module(path, name):
    assert path.is_file(), f"Missing consumer implementation: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def consumer(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SHARED))
    monkeypatch.setenv("EASEL_ROOT", str(tmp_path))
    import output_paths

    monkeypatch.setattr(output_paths, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(output_paths, "OUTPUTS_DIR", tmp_path / "outputs")
    kit = tmp_path / "skills/openclaw" / SKILL / "vendor/xiaoheihe-publisher"
    scripts = kit / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "xhh_publish.py").write_text(
        "import json, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "root = pathlib.Path(__file__).parents[1]\n"
        "with (root / 'calls.jsonl').open('a', encoding='utf-8') as f:\n"
        "    f.write(json.dumps(args) + '\\n')\n"
        "if args[0] == 'show':\n"
        "    print((pathlib.Path(args[1]) / 'plan.json').read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print(json.dumps({'state': 'acknowledged', 'argv': args}))\n",
        encoding="utf-8",
    )
    operation = tmp_path / "outputs/game-review/assets/xhh-operation"
    operation.mkdir(parents=True)
    plan = {"approval_sha256": DIGEST,
            "spec": {"title": "Review", "content": "Game notes", "hashtags": ["games"]}}
    (operation / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    return ADAPTER, kit, operation, plan


def calls(kit):
    path = kit / "calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_submit_requires_explicit_exec_before_any_child(consumer):
    adapter, kit, op, _ = consumer
    adapter = load_module(adapter, "easel_xhh_adapter")
    assert adapter.main(["submit", str(op), "--approval", DIGEST]) == 2
    assert calls(kit) == []


@pytest.mark.parametrize("field", ["title", "content", "hashtags"])
def test_guard_refuses_frozen_outgoing_content_before_submit(consumer, field):
    adapter, kit, op, plan = consumer
    adapter = load_module(adapter, "easel_xhh_adapter")
    value = "EASEL_ROOT"
    plan["spec"][field] = [value] if field == "hashtags" else value
    (op / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        adapter.main(["submit", str(op), "--approval", DIGEST, "--exec"])
    assert exc.value.code == 7
    assert calls(kit) == [["show", str(op)]]


@pytest.mark.parametrize("content", [
    "<p>EASEL&#95;ROOT</p>", "<p>EASEL_<b>ROOT</b></p>",
    "<p>Bearer</p><p>abcdefghijklmnopqrstuvwx</p>",
])
def test_guard_scans_rendered_html_before_submit(consumer, content):
    adapter, kit, op, plan = consumer
    adapter = load_module(adapter, "easel_xhh_adapter")
    plan["spec"].update(content=content, content_format="html")
    (op / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        adapter.main(["submit", str(op), "--approval", DIGEST, "--exec"])
    assert exc.value.code == 7
    assert calls(kit) == [["show", str(op)]]


def test_approval_mismatch_never_dispatches_submit(consumer):
    adapter, kit, op, _ = consumer
    adapter = load_module(adapter, "easel_xhh_adapter")
    assert adapter.main(["submit", str(op), "--approval", "b" * 64, "--exec"]) == 2
    assert calls(kit) == [["show", str(op)]]


def test_submit_forwards_exact_digest_and_confirm_once(consumer, monkeypatch):
    adapter, kit, op, _ = consumer
    adapter = load_module(adapter, "easel_xhh_adapter")
    run = adapter.subprocess.run
    invocations = []

    def capture(argv, **kwargs):
        invocations.append((argv, kwargs))
        return run(argv, **kwargs)

    monkeypatch.setattr(adapter.subprocess, "run", capture)
    assert adapter.main(["submit", str(op), "--approval", DIGEST, "--exec"]) == 0
    assert calls(kit) == [["show", str(op)],
                          ["submit", str(op), "--approval", DIGEST, "--confirm"]]
    for argv, kwargs in invocations:
        assert isinstance(argv, list) and argv[0] == sys.executable
        assert not kwargs.get("shell", False)
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["env"]["PYTHONUTF8"] == "1"


@pytest.mark.parametrize("command", ["show", "submit", "reconcile"])
def test_operation_must_stay_inside_outputs(consumer, tmp_path, command):
    adapter, kit, _, _ = consumer
    adapter = load_module(adapter, "easel_xhh_adapter")
    argv = [command, str(tmp_path / "outside")]
    if command == "submit":
        argv += ["--approval", DIGEST, "--exec"]
    assert adapter.main(argv) == 2
    assert calls(kit) == []


def test_plan_validates_output_and_preserves_literal_arguments(consumer, tmp_path):
    adapter, kit, _, _ = consumer
    adapter = load_module(adapter, "easel_xhh_adapter")
    spec = tmp_path / "spec with spaces.json"
    spec.write_text("{}")
    assert adapter.main(["plan", str(spec), "--account", "alias & literal",
                         "--mode", "draft", "--out", "outside"]) == 2
    assert calls(kit) == []
    out = tmp_path / "outputs/game-review/assets/new-operation"
    assert adapter.main(["plan", str(spec), "--account", "alias & literal",
                         "--mode", "draft", "--out", str(out)]) == 0
    assert calls(kit) == [["plan", str(spec), "--account", "alias & literal",
                          "--mode", "draft", "--out", str(out)]]


def test_copied_workspace_finds_kit_without_original_source(consumer, tmp_path, monkeypatch):
    adapter_path, kit, op, _ = consumer
    assert adapter_path.is_file(), "Missing consumer implementation"
    workspace = tmp_path / "workspace"
    target = workspace / "shared/scripts"
    target.mkdir(parents=True)
    for name in ("xiaoheihe_publish.py", "content_guard.py", "output_paths.py"):
        shutil.copyfile(SHARED / name, target / name)
    copied = workspace / "skills" / SKILL / "vendor/xiaoheihe-publisher"
    shutil.copytree(kit, copied)
    monkeypatch.delenv("EASEL_ROOT")
    adapter = load_module(target / "xiaoheihe_publish.py", "workspace_xhh_adapter")
    assert adapter.main(["show", str(op)]) == 0
    assert calls(copied) == [["show", str(op)]]
    assert calls(kit) == []


def test_skill_is_discovered_without_native_web_platform_registration():
    sys.path.insert(0, str(ROOT))
    from easel.commands import skill

    assert skill._find_skill("xiaoheihe-publisher") == SKILL
    assert SKILL in skill._list_all_skills()
    dispatch = load_module(ROOT / "skills/openclaw/skill-cross-platform-publish/scripts/publish_dispatch.py",
                           "xhh_dispatch")
    route = dispatch._check_platform("xiaoheihe", {"media_type": "image"})
    assert route["ok"] and route["publisher"] == SKILL
    assert "'skill-xiaoheihe-publisher':" in (ROOT / "web/frontend/src/lib/skillDisplayNames.ts").read_text(encoding="utf-8")
    validator = load_module(ROOT / "scripts/validate_skills.py", "xhh_validator")
    assert "skills/shared/scripts/xiaoheihe_publish.py" in validator.PUBLISH_SCRIPT_CONTRACTS


def test_web_skill_discovery_keeps_native_platform_backends_unchanged(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "web"))
    monkeypatch.syspath_prepend(str(ROOT))
    import app

    monkeypatch.setattr(app, "_read_env", lambda: {})
    assert app.find_skill("xiaoheihe-publisher") == SKILL
    found = next(item for item in app.get_skills() if item["name"] == SKILL)
    assert found["layer"] == "publish"
    assert "小黑盒" in found["description"]
    assert "xiaoheihe" not in app.LOGIN_RUNNERS


def test_documented_spec_plans_with_the_real_bundled_cli(tmp_path):
    folder = ROOT / "skills/openclaw" / SKILL
    guide = (folder / "references/publishing.md").read_text(encoding="utf-8")
    snippet = re.search(r"```json\s*\n(.*?)\n```", guide, re.S).group(1)
    spec = json.loads(snippet)
    (tmp_path / "cover.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="))
    inputs = tmp_path / "assets"
    inputs.mkdir()
    input_path = inputs / "post.json"
    input_path.write_text(snippet, encoding="utf-8")
    script = folder / "vendor/xiaoheihe-publisher/scripts/xhh_publish.py"
    result = subprocess.run(
        [sys.executable, "-I", str(script), "plan", str(input_path),
         "--account", "offline-test", "--mode", "draft", "--out", str(tmp_path / "operation")],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    frozen = json.loads((tmp_path / "operation/plan.json").read_text(encoding="utf-8"))
    assert frozen["spec"]["content"] == spec["content"]
    assert frozen["spec"]["post_type"] == "1"


@pytest.mark.parametrize("configured", [True, False])
def test_real_copied_cli_plan_and_tamper_refusal_from_unrelated_cwd(tmp_path, configured):
    upstream = ROOT / "skills/openclaw" / SKILL / "vendor/xiaoheihe-publisher"
    assert (upstream / "kit-manifest.json").is_file(), "Stable upstream kit not imported yet"
    workspace = tmp_path / "workspace"
    script_dir = workspace / "shared/scripts"
    script_dir.mkdir(parents=True)
    for name in ("xiaoheihe_publish.py", "content_guard.py", "output_paths.py"):
        shutil.copyfile(SHARED / name, script_dir / name)
    copied = workspace / "skills" / SKILL / "vendor/xiaoheihe-publisher"
    shutil.copytree(upstream, copied)
    project = tmp_path / "project" if configured else workspace
    if configured:
        shutil.copytree(upstream, project / "skills/openclaw" / SKILL / "vendor/xiaoheihe-publisher")
    content = project / "outputs/game-review/assets"
    content.mkdir(parents=True)
    spec = content / "post.json"
    image = content / "cover.png"
    image_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
    image.write_bytes(image_bytes)
    spec.write_text(json.dumps({"title": "小黑盒测试", "content": "冻结图片与中文正文", "hashtags": ["游戏"],
                               "images": ["cover.png"]}),
                    encoding="utf-8")
    op = content / "operation"
    cwd = tmp_path / "unrelated"
    cwd.mkdir()
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    env.pop("EASEL_ROOT", None)
    if configured:
        env["EASEL_ROOT"] = str(project)
    runner = script_dir / "xiaoheihe_publish.py"

    def run(script, *args):
        return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True,
                              text=True, encoding="utf-8", env=env, cwd=cwd, timeout=30)

    version = run(copied / "scripts/xhh_cli.py", "--version")
    assert version.returncode == 0, version.stderr
    assert "0.5.0rc4+standalone.7" in version.stdout
    planned = run(runner, "plan", spec, "--account", "offline-test", "--mode", "public", "--out", op)
    assert planned.returncode == 0, planned.stdout + planned.stderr
    shown = run(runner, "show", op)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    frozen = json.loads(shown.stdout)
    assert frozen["spec"]["content"] == "冻结图片与中文正文"
    assert frozen["account"] == "offline-test" and frozen["mode"] == "public"
    media = op / frozen["media"][0]["path"]
    assert media.read_bytes() == image_bytes
    image.write_bytes(b"source changed after planning")
    assert run(runner, "show", op).returncode == 0
    assert media.read_bytes() == image_bytes
    approval = frozen["approval_sha256"]
    frozen["spec"]["content"] = "Changed after approval"
    (op / "plan.json").write_text(json.dumps(frozen), encoding="utf-8")
    refused = run(runner, "submit", op, "--approval", approval, "--exec")
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert not (op / "attempt.json").exists()
    for source in upstream.rglob("*"):
        if source.is_file():
            assert (copied / source.relative_to(upstream)).read_bytes() == source.read_bytes()
