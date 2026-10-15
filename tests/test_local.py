import json
import subprocess
from pathlib import Path

import pytest

from review_personas.cli import EXIT_OK, EXIT_RETRY, main
from review_personas.local import finish, prepare
from review_personas.render import MARKER

ROOT = Path(__file__).resolve().parents[1]
GOOD = '{"relevant": true, "score": 8, "summary": "Fine.", "findings": []}'
NOT_RELEVANT = '{"relevant": false, "summary": "Nothing for me."}'


@pytest.fixture
def repo(tmp_path):
    def run(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q", "-b", "main")
    run("config", "user.email", "t@e.com")
    run("config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    run("add", "-A")
    run("commit", "-qm", "base")
    run("switch", "-qc", "feature")
    (tmp_path / "a.py").write_text("x = 2\n")  # uncommitted
    (tmp_path / ".env").write_text("SECRET=hunter2\n")  # untracked and sensitive
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/review-personas.yml").write_text(
        "personas:\n  ui-developer: {paths: ['*.tsx']}\n"
    )
    return tmp_path


def write_replies(out, replies):
    for r in out["reviews"]:
        Path(r["reply_file"]).write_text(replies[r["id"]])


# LOC-2, LOC-3, LOC-5, DAT-1
def test_prepare_finish_round_trip(repo, tmp_path_factory):
    work = tmp_path_factory.mktemp("work")
    before = sorted(p.name for p in repo.iterdir())
    out = prepare(repo, base="main", out_dir=work)
    assert "branch feature vs main" in out["reviewed"]
    ids = [r["id"] for r in out["reviews"]]
    assert ids == ["app-developer", "aws-architect", "dba"]  # ui-developer skipped by paths
    prompt = Path(out["reviews"][0]["prompt_file"]).read_text()
    assert "+x = 2" in prompt and "hunter2" not in prompt and ".env (sensitive)" in prompt
    assert prompt.startswith("<instructions>")

    write_replies(out, {"app-developer": GOOD, "aws-architect": NOT_RELEVANT, "dba": "junk"})
    first = finish(work)
    assert [r["id"] for r in first["retry"]] == ["dba"]
    assert "could not be used" in first["retry"][0]["message"]

    Path(first["retry"][0]["reply_file"]).write_text("still junk")
    final = finish(work)["review"]
    assert final.startswith(MARKER) and "8.0/10 (advisory)" in final
    assert "| 🗄️ DBA | ⚠️ | Review failed: Invalid reply after retry" in final
    assert "Not relevant: no matching files" in final
    assert "Tokens" not in final
    assert not work.exists()  # temp dir removed
    assert sorted(p.name for p in repo.iterdir()) == before  # nothing written in the repo


def test_cli_prepare_and_finish(repo, capsys):
    assert main(["prepare", "--repo-root", str(repo), "--base", "main"]) == EXIT_OK
    out = json.loads(capsys.readouterr().out)
    write_replies(out, {r["id"]: "junk" for r in out["reviews"]})
    assert main(["finish", out["dir"]]) == EXIT_RETRY
    capsys.readouterr()
    write_replies(out, {r["id"]: GOOD for r in out["reviews"]})
    assert main(["finish", out["dir"]]) == EXIT_OK
    assert MARKER in capsys.readouterr().out


def test_cli_prepare_config_error(repo, capsys):
    (repo / ".github/review-personas.yml").write_text("bogus: 1\n")
    assert main(["prepare", "--repo-root", str(repo), "--base", "main"]) == 2
    assert "Unknown config keys" in capsys.readouterr().err


def test_plugin_files_are_consistent():
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert marketplace["plugins"][0]["name"] == plugin["name"] == "review-personas"
    assert marketplace["plugins"][0]["source"] == "./"  # the repo root is the plugin
    command = (ROOT / "commands/review-personas.md").read_text()
    assert 'uvx --from "${CLAUDE_PLUGIN_ROOT}" review-personas prepare' in command
    assert "persona-reviewer" in command
    agent = (ROOT / "agents/persona-reviewer.md").read_text()
    assert "name: persona-reviewer" in agent and "tools: Read" in agent
