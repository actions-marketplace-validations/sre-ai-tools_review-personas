"""Decide which changed files each persona sees (design D4 filtering order, D5 paths)."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase

from .changes import FileChange

SENSITIVE = "sensitive"
GENERATED = "generated/binary"
SIZE_LIMIT = "size limit"


@dataclass(frozen=True)
class NotReviewed:
    path: str
    reason: str


@dataclass
class PersonaDiff:
    text: str
    files: list[str] = field(default_factory=list)
    not_reviewed: list[NotReviewed] = field(default_factory=list)  # size limit only


def matches(path: str, patterns: tuple[str, ...] | list[str]) -> bool:
    """Shell-style globs on the repo-relative path; `*` crosses directories.

    A pattern without "/" also matches the file name at any depth, like .gitignore.
    """
    name = path.rsplit("/", 1)[-1]
    return any(
        fnmatchcase(path, p)
        or fnmatchcase("/" + path, p)
        or ("/" not in p and fnmatchcase(name, p))
        for p in patterns
    )


def global_filter(
    files: list[FileChange], sensitive: tuple[str, ...], generated: tuple[str, ...]
) -> tuple[list[FileChange], list[NotReviewed]]:
    """Stages 1-2: files no persona may see, with the reason."""
    kept, skipped = [], []
    for f in files:
        names = [f.path] + ([f.old_path] if f.old_path else [])
        if any(matches(n, sensitive) for n in names):
            skipped.append(NotReviewed(f.path, SENSITIVE))
        elif f.binary or matches(f.path, generated):
            skipped.append(NotReviewed(f.path, GENERATED))
        else:
            kept.append(f)
    return kept, skipped


def persona_diff(
    files: list[FileChange], paths: tuple[str, ...] | None, max_chars: int
) -> PersonaDiff:
    """Stages 3-4: the persona's path filter, then whole files up to max_chars.

    Files outside the persona's paths are out of scope, not "not reviewed".
    """
    scoped = files if paths is None else [f for f in files if matches(f.path, paths)]
    out = PersonaDiff(text="")
    parts, size = [], 0
    for f in scoped:
        label = f"{f.old_path} -> {f.path}" if f.old_path else f.path
        chunk = f"--- {label} ({f.status})\n{f.patch}\n"
        if size + len(chunk) > max_chars:
            out.not_reviewed.append(NotReviewed(f.path, SIZE_LIMIT))
            continue
        parts.append(chunk)
        out.files.append(f.path)
        size += len(chunk)
    out.text = "".join(parts)
    return out
