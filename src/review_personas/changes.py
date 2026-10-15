"""Collect a change set with `git diff` - the only diff source, in CI and locally (design D4)."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

BINARY_SNIFF_BYTES = 8000


@dataclass(frozen=True)
class FileChange:
    path: str
    status: str  # added | modified | removed | renamed
    patch: str | None  # None for binary files
    old_path: str | None = None  # set for renames

    @property
    def binary(self) -> bool:
        return self.patch is None


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def _diff(repo: Path, *revs: str) -> list[FileChange]:
    return parse_unified_diff(git(repo, "diff", "--no-color", "--no-ext-diff", "-M", *revs))


def ci_changes(repo: Path, base_ref: str, head: str = "HEAD") -> list[FileChange]:
    """Exactly the PR's commits: merge base of base_ref and head, compared with head."""
    merge_base = git(repo, "merge-base", base_ref, head).strip()
    return _diff(repo, merge_base, head)


def default_base(repo: Path) -> str:
    try:
        return git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    except GitError:
        for candidate in ("origin/main", "origin/master", "main", "master"):
            try:
                git(repo, "rev-parse", "--verify", "--quiet", candidate)
                return candidate
            except GitError:
                continue
    raise GitError("Could not find a base branch; pass one explicitly (e.g. --base main)")


def local_changes(repo: Path, base_ref: str | None = None) -> tuple[list[FileChange], str]:
    """Committed and uncommitted changes since the merge base, plus untracked files.

    Read-only: nothing is staged or modified.
    """
    base_ref = base_ref or default_base(repo)
    merge_base = git(repo, "merge-base", base_ref, "HEAD").strip()
    files = _diff(repo, merge_base)
    seen = {f.path for f in files}
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    for path in filter(None, untracked):
        if path not in seen:
            files.append(_untracked(repo, path))
    return files, base_ref


def _untracked(repo: Path, path: str) -> FileChange:
    data = (repo / path).read_bytes()
    if b"\0" in data[:BINARY_SNIFF_BYTES]:
        return FileChange(path, "added", None)
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return FileChange(path, "added", None)
    patch = f"@@ -0,0 +1,{len(lines)} @@\n" + "\n".join("+" + line for line in lines)
    return FileChange(path, "added", patch)


_HEADER = re.compile(r"^diff --git ", re.MULTILINE)
_HEADER_PATHS = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def parse_unified_diff(text: str) -> list[FileChange]:
    files = []
    starts = [m.start() for m in _HEADER.finditer(text)]
    for i, start in enumerate(starts):
        section = text[start : starts[i + 1] if i + 1 < len(starts) else len(text)]
        lines = section.splitlines()
        old = new = None
        rename_from = rename_to = None
        for line in lines[1:]:
            if line.startswith("@@"):
                break
            if line.startswith("--- a/"):
                old = line[6:]
            elif line.startswith("+++ b/"):
                new = line[6:]
            elif line.startswith("rename from "):
                rename_from = line[12:]
            elif line.startswith("rename to "):
                rename_to = line[10:]
        if not (old or new or rename_to):
            m = _HEADER_PATHS.match(lines[0])
            if m:
                old, new = m.group(1), m.group(2)
        head = section.split("\n@@", 1)[0]
        if "\nnew file mode" in head:
            status, path = "added", new
        elif "\ndeleted file mode" in head:
            status, path = "removed", old
        elif rename_to:
            status, path = "renamed", rename_to
        else:
            status, path = "modified", new or old
        hunk = section.find("\n@@")
        patch = section[hunk + 1 :].rstrip("\n") if hunk != -1 else None
        if patch is None and "Binary files" not in head and status == "renamed":
            patch = ""  # pure rename, no content change
        files.append(
            FileChange(
                path=path,
                status=status,
                patch=patch,
                old_path=rename_from if status == "renamed" else None,
            )
        )
    return files
