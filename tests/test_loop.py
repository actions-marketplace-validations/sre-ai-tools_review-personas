"""`review-personas loop save | check` (0005 D5, FIX-2, FIX-3)."""

import json
import sys

import pytest

from review_personas.cli import main
from review_personas.loop import (
    EXIT_NOT_PROVED,
    EXIT_PROVED,
    EXIT_UNRESTORED,
    LoopError,
    check,
    save,
)

# The "test" checks that calc.py doubles correctly. Pre-fix, it adds instead.
TEST = f'{sys.executable} -c "import calc, sys; sys.exit(0 if calc.double(3) == 6 else 1)"'
BROKEN = "def double(x):\n    return x + 2\n"
FIXED = "def double(x):\n    return x * 2\n"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "calc.py").write_text(BROKEN)
    (root / "notes.txt").write_text("uncommitted work in progress\n")
    return root


@pytest.fixture
def state(tmp_path):
    return tmp_path / "state"


def fix(repo, state):
    save(state, repo, ["calc.py"])
    (repo / "calc.py").write_text(FIXED)


def test_proves_the_test_fails_without_the_fix_and_restores_it(repo, state):
    fix(repo, state)
    result = check(state, repo, TEST)
    assert result.code == EXIT_PROVED and result.test_failed_without_fix
    assert (repo / "calc.py").read_text() == FIXED
    assert not (state / "saved.json").exists()  # cleared for the next fix


def test_leaves_files_it_was_not_given_alone(repo, state):
    fix(repo, state)
    before = (repo / "notes.txt").read_bytes()
    check(state, repo, TEST)
    assert (repo / "notes.txt").read_bytes() == before


def test_a_test_that_passes_without_the_fix_proves_nothing(repo, state):
    fix(repo, state)
    result = check(state, repo, f'{sys.executable} -c "pass"')
    assert result.code == EXIT_NOT_PROVED and not result.test_failed_without_fix
    assert (repo / "calc.py").read_text() == FIXED
    assert (state / "saved.json").exists()  # kept, so a rewritten test can be checked


def test_saving_twice_keeps_the_original(repo, state):
    save(state, repo, ["calc.py"])
    (repo / "calc.py").write_text("partial edit\n")
    save(state, repo, ["calc.py"])
    (repo / "calc.py").write_text(FIXED)
    assert check(state, repo, TEST).code == EXIT_PROVED


def test_a_file_the_fix_creates_is_removed_then_restored(repo, state):
    save(state, repo, ["helpers.py"])
    (repo / "helpers.py").write_text("X = 1\n")
    exists = "import os, sys; sys.exit(0 if os.path.exists('helpers.py') else 1)"
    probe = f'{sys.executable} -c "{exists}"'
    assert check(state, repo, probe).code == EXIT_PROVED
    assert (repo / "helpers.py").read_text() == "X = 1\n"


def test_restores_even_when_the_test_times_out(repo, state):
    fix(repo, state)
    slow = f'{sys.executable} -c "import time; time.sleep(5)"'
    with pytest.raises(LoopError, match="longer than"):
        check(state, repo, slow, timeout=0.5)
    assert (repo / "calc.py").read_text() == FIXED


def test_reports_a_file_it_could_not_restore(repo, state, monkeypatch):
    fix(repo, state)
    import review_personas.loop as loop

    real_write = loop._write

    def flaky(path, data):
        if path.name == "calc.py" and data == FIXED.encode():
            raise OSError("disk full")
        real_write(path, data)

    monkeypatch.setattr(loop, "_write", flaky)
    result = check(state, repo, TEST)
    assert result.code == EXIT_UNRESTORED and result.unrestored == ["calc.py"]
    assert (state / "fixed" / "0").read_text() == FIXED  # the copy is kept for recovery


def test_refuses_paths_outside_the_repo_and_an_empty_state(repo, state):
    with pytest.raises(LoopError, match="outside"):
        save(state, repo, ["../elsewhere.py"])
    with pytest.raises(LoopError, match="nothing saved"):
        check(state, repo, TEST)


def test_cli(repo, state, capsys):
    args = ["--repo-root", str(repo)]
    assert main(["loop", "save", str(state), "calc.py", *args]) == 0
    assert json.loads(capsys.readouterr().out) == {"saved": ["calc.py"]}
    (repo / "calc.py").write_text(FIXED)
    assert main(["loop", "check", str(state), "--test", TEST, *args]) == EXIT_PROVED
    out = json.loads(capsys.readouterr().out)
    assert out["test_failed_without_fix"] is True and out["unrestored"] == []
    assert main(["loop", "check", str(state), "--test", TEST, *args]) == 2  # nothing saved now
