import subprocess

import pytest

from review_personas.changes import FileChange, GitError, ci_changes, local_changes
from review_personas.filtering import (
    GENERATED,
    SENSITIVE,
    SIZE_LIMIT,
    global_filter,
    matches,
    persona_diff,
)


def run(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    run(tmp_path, "init", "-q", "-b", "main")
    run(tmp_path, "config", "user.email", "t@example.com")
    run(tmp_path, "config", "user.name", "t")
    (tmp_path / "keep.py").write_text("a = 1\n")
    (tmp_path / "old.py").write_text("gone = True\n")
    (tmp_path / "move_me.txt").write_text("same content\n" * 5)
    (tmp_path / ".gitignore").write_text("ignored.log\n")
    run(tmp_path, "add", "-A")
    run(tmp_path, "commit", "-qm", "base")
    run(tmp_path, "switch", "-qc", "feature")
    (tmp_path / "keep.py").write_text("a = 2\n")
    run(tmp_path, "rm", "-q", "old.py")
    run(tmp_path, "mv", "move_me.txt", "moved.txt")
    (tmp_path / "db").mkdir()
    (tmp_path / "db/001.sql").write_text("CREATE TABLE t (id int);\n")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\0\0binary")
    run(tmp_path, "add", "-A")
    run(tmp_path, "commit", "-qm", "feature")
    return tmp_path


def by_path(files):
    return {f.path: f for f in files}


def test_ci_changes_are_exactly_the_commits(repo):
    (repo / "uncommitted.py").write_text("x = 1\n")  # must not appear in CI mode
    files = by_path(ci_changes(repo, "main"))
    assert set(files) == {"keep.py", "old.py", "moved.txt", "db/001.sql", "logo.png"}
    assert files["keep.py"].status == "modified" and "+a = 2" in files["keep.py"].patch
    assert files["old.py"].status == "removed"
    assert files["moved.txt"].status == "renamed" and files["moved.txt"].old_path == "move_me.txt"
    assert files["db/001.sql"].status == "added"
    assert files["logo.png"].binary


def test_local_changes_include_uncommitted_and_untracked(repo):
    (repo / "keep.py").write_text("a = 3\n")  # unstaged edit
    (repo / "new.py").write_text("print('hi')\n")  # untracked
    (repo / "ignored.log").write_text("noise\n")  # git-ignored
    files, base = local_changes(repo, "main")
    files = by_path(files)
    assert base == "main"
    assert "+a = 3" in files["keep.py"].patch
    assert files["new.py"].status == "added" and "+print('hi')" in files["new.py"].patch
    assert "ignored.log" not in files
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo)
    assert staged.returncode == 0  # read-only: nothing was staged


def test_local_untracked_symlinks_and_nested_repos_are_not_read(repo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_text("TOP SECRET\n")
    (repo / "link.txt").symlink_to(outside)
    run(repo / "..", "init", "-q", str(repo / "nested"))
    (repo / "nested/inner.py").write_text("y = 1\n")
    files = by_path(local_changes(repo, "main")[0])
    assert files["link.txt"].binary and files["nested"].binary
    assert not any("TOP SECRET" in (f.patch or "") for f in files.values())


def test_local_changes_without_base_branch(tmp_path):
    run(tmp_path, "init", "-q", "-b", "trunk")
    run(tmp_path, "commit", "-q", "--allow-empty", "-m", "x", "--author", "t <t@e.com>")
    with pytest.raises(GitError, match="base branch"):
        local_changes(tmp_path)


def fc(path, patch="@@ -1 +1 @@\n+x", old_path=None):
    return FileChange(path, "renamed" if old_path else "modified", patch, old_path)


def test_matches():
    assert matches("app/.env", (".env",))
    assert matches("deep/a/b.sql", ("*.sql",))
    assert matches("templates/x.html", ("*/templates/*",))
    assert matches("web/a/App.tsx", ("web/*",))
    assert not matches("src/web/App.tsx", ("web/*",))


# DAT-1, COM-3: sensitive and generated/binary files are removed with a reason
def test_global_filter():
    files = [
        fc("app/.env"),
        fc("public.txt", old_path="secrets/id_rsa"),  # renamed away from a sensitive name
        fc("package-lock.json"),
        fc("img.png", patch=None),
        fc("src/main.py"),
    ]
    kept, skipped = global_filter(files, (".env", "id_rsa*"), ("package-lock.json",))
    assert [f.path for f in kept] == ["src/main.py"]
    assert [(s.path, s.reason) for s in skipped] == [
        ("app/.env", SENSITIVE),
        ("public.txt", SENSITIVE),
        ("package-lock.json", GENERATED),
        ("img.png", GENERATED),
    ]


# D5 paths, DAT-4 whole files only
def test_persona_diff_paths_and_size_limit():
    files = [fc("a.py", "x" * 50), fc("b.py", "y" * 500), fc("c.py", "z" * 10), fc("web/d.css")]
    d = persona_diff(files, None, max_chars=150)
    assert d.files == ["a.py", "c.py", "web/d.css"]
    assert [(n.path, n.reason) for n in d.not_reviewed] == [("b.py", SIZE_LIMIT)]
    assert "yyy" not in d.text
    scoped = persona_diff(files, ("web/*",), max_chars=150)
    assert scoped.files == ["web/d.css"] and scoped.not_reviewed == []
