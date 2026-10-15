import json

import pytest

from review_personas.changes import FileChange
from review_personas.cli import EXIT_BROKEN, EXIT_CONFIG, EXIT_OK, main
from review_personas.config import Persona, Settings
from review_personas.github import GitHub
from review_personas.llm import Completion
from review_personas.render import MARKER
from review_personas.result import Usage
from review_personas.runner import ALL_TOO_LARGE, pipeline_broken, plan_reviews, review, run_plans

GOOD = '{"relevant": true, "score": 6, "summary": "Needs an index.", "findings": []}'
NOT_RELEVANT = '{"relevant": false, "summary": "No SQL."}'


class FakeLLM:
    """Replies per persona name, in order; an Exception instance is raised."""

    def __init__(self, replies):
        self.replies = {k: list(v) for k, v in replies.items()}
        self.calls = []

    def complete(self, *, model, system, messages, model_params):
        name = system.split("You are the ", 1)[1].split(" on a", 1)[0]
        self.calls.append((name, messages))
        reply = self.replies[name].pop(0)
        if isinstance(reply, Exception):
            raise reply
        text, stop = reply if isinstance(reply, tuple) else (reply, "end_turn")
        return Completion(text, stop, Usage(100, 10))


def persona(name, paths=None):
    return Persona(id=name.lower(), name=name, icon="", focus="f", model="m", paths=paths)


FILES = [
    FileChange("db/001.sql", "added", "@@ -0,0 +1 @@\n+CREATE TABLE t (id int);"),
    FileChange(".env", "added", "@@ -0,0 +1 @@\n+SECRET=1"),
]


def plan_one(p, files=FILES, max_chars=100_000):
    settings = Settings(personas=(p,), max_diff_chars=max_chars)
    plans, skipped = plan_reviews(settings, files, title="t", body="b")
    return plans[0], skipped


# DAT-1: sensitive file never reaches a prompt; D5: paths skip without a call
def test_plan_filters_and_paths():
    plan, skipped = plan_one(persona("DBA"))
    assert "SECRET" not in plan.prompt.user and ".env (sensitive)" in plan.prompt.user
    assert [s.path for s in skipped] == [".env"]
    ui, _ = plan_one(persona("UI", paths=("*.tsx",)))
    assert ui.prompt is None and ui.skipped_by_paths
    big, _ = plan_one(persona("DBA"), max_chars=10)
    assert big.prompt is None and big.error == ALL_TOO_LARGE
    only_secret, _ = plan_one(persona("DBA"), files=FILES[1:])
    assert only_secret.prompt is None and only_secret.result().verdict.relevant is False


def test_retry_once_then_succeed():
    llm = FakeLLM({"DBA": ["oops", GOOD]})
    r = review(plan_one(persona("DBA"))[0], llm)
    assert r.verdict.score == 6 and r.error is None and r.usage == Usage(200, 20)
    assert [m["role"] for m in llm.calls[1][1]] == ["user", "assistant", "user"]


@pytest.mark.parametrize(
    "replies, error",
    [
        (["bad", "still bad"], "Invalid reply after retry"),
        ([("{", "max_tokens")], "Model hit its output token limit"),
        ([RuntimeError("AccessDenied\nstack trace line")], "RuntimeError: AccessDenied"),
    ],
)
def test_failures_become_errors(replies, error):
    r = review(plan_one(persona("DBA"))[0], FakeLLM({"DBA": replies}))
    assert r.error.startswith(error) and "stack trace" not in r.error


# D10: broken only when every persona that called the model failed
def test_pipeline_broken():
    settings = Settings(personas=(persona("DBA"), persona("App"), persona("UI", ("*.tsx",))))
    plans, _ = plan_reviews(settings, FILES, title="t", body="")
    ok = run_plans(plans, FakeLLM({"DBA": [GOOD], "App": [RuntimeError("x")]}))
    assert not pipeline_broken(plans, ok)
    bad = run_plans(plans, FakeLLM({"DBA": [RuntimeError("x")], "App": [RuntimeError("x")]}))
    assert pipeline_broken(plans, bad)


class FakeGitHub:
    def __init__(self, fail=False):
        self.posted, self.fail = [], fail

    def upsert_comment(self, pr, body):
        if self.fail:
            raise RuntimeError("403")
        self.posted.append((pr, body))
        return "created"


@pytest.fixture
def git_repo(tmp_path):
    import subprocess

    def run(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q", "-b", "main")
    run("config", "user.email", "t@e.com")
    run("config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    run("add", "-A")
    run("commit", "-qm", "base")
    run("switch", "-qc", "f")
    (tmp_path / "db.sql").write_text("CREATE TABLE t (id int);\n")
    run("add", "-A")
    run("commit", "-qm", "f")
    return tmp_path


def ci(monkeypatch, repo, llm, gh, *extra, event=None, tmp_path=None):
    import review_personas.cli as cli

    if event is not None:
        path = repo / "event.json"
        path.write_text(json.dumps({"pull_request": event}))
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))
    else:
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    args = cli.build_parser().parse_args(["ci", "--repo-root", str(repo), *extra])
    return cli.cmd_ci(args, llm=llm, github=gh)


ALL = {
    "AWS architect": [NOT_RELEVANT],
    "App developer": [GOOD],
    "UI developer": [NOT_RELEVANT],
    "DBA": [GOOD],
}
EVENT = {"number": 7, "title": "Add table", "body": "", "base": {"ref": "main"}, "head": {}}


def test_ci_posts_comment(monkeypatch, git_repo):
    gh = FakeGitHub()
    code = ci(monkeypatch, git_repo, FakeLLM(ALL), gh, "--base-ref", "main", event=EVENT)
    assert code == EXIT_OK
    pr, body = gh.posted[0]
    assert pr == 7 and body.startswith(MARKER) and "6.0/10 (advisory)" in body


def test_ci_exit_codes(monkeypatch, git_repo):
    broken = {k: [RuntimeError("AccessDenied")] for k in ALL}
    assert (
        ci(monkeypatch, git_repo, FakeLLM(broken), FakeGitHub(), "--base-ref", "main", event=EVENT)
        == EXIT_BROKEN
    )
    assert (
        ci(
            monkeypatch,
            git_repo,
            FakeLLM(ALL),
            FakeGitHub(fail=True),
            "--base-ref",
            "main",
            event=EVENT,
        )
        == EXIT_BROKEN
    )
    (git_repo / ".github").mkdir()
    (git_repo / ".github/review-personas.yml").write_text("bogus: 1\n")
    assert ci(monkeypatch, git_repo, FakeLLM(ALL), FakeGitHub(), event=EVENT) == EXIT_CONFIG


def test_ci_dry_run_prints(monkeypatch, git_repo, capsys):
    code = ci(monkeypatch, git_repo, FakeLLM(ALL), None, "--base-ref", "main", "--dry-run")
    assert code == EXIT_OK and MARKER in capsys.readouterr().out


def test_main_requires_subcommand():
    with pytest.raises(SystemExit):
        main([])


# COM-2: edit the existing bot comment instead of adding one
def test_upsert_edits_existing(monkeypatch):
    gh = GitHub("t", "o/r")
    comments = [
        {"id": 1, "body": MARKER + " by a human", "user": {"type": "User"}},
        {"id": 2, "body": MARKER + " old", "user": {"type": "Bot"}},
    ]
    calls = []

    class Resp:
        links = {}

        def raise_for_status(self):
            pass

        def json(self):
            return comments

    monkeypatch.setattr(gh.session, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(gh.session, "patch", lambda url, **k: calls.append(url) or Resp())
    monkeypatch.setattr(gh.session, "post", lambda url, **k: calls.append(url) or Resp())
    assert gh.upsert_comment(7, MARKER + " new") == "updated"
    assert calls == ["https://api.github.com/repos/o/r/issues/comments/2"]
    comments.pop()
    assert gh.upsert_comment(7, MARKER + " new") == "created"


# D8/CI-4: a hung persona can't stop the others from being reported
def test_deadline_reports_slow_personas_as_timed_out():
    import threading

    release = threading.Event()

    class SlowForApp(FakeLLM):
        def complete(self, **kwargs):
            if "App" in kwargs["system"]:
                release.wait(5)  # simulates a hung Bedrock call
            return super().complete(**kwargs)

    settings = Settings(personas=(persona("DBA"), persona("App")))
    plans, _ = plan_reviews(settings, FILES, title="t", body="")
    results = run_plans(plans, SlowForApp({"DBA": [GOOD], "App": [GOOD]}), deadline_s=0.3)
    release.set()
    assert results[0].verdict.score == 6 and results[0].error is None
    assert results[1].error == "Timed out after 0.3s"
    assert not pipeline_broken(plans, results)
