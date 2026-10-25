"""Proof that a test fails without its fix, for /prpanel:review-loop (0005 D5, FIX-2, FIX-3).

`save` keeps the pre-fix content of the code files a fix will change, before the session edits
them. `check` writes that content back, runs the test, and always puts the fixed content back,
then checks each file's SHA-256. It never runs git and never writes a file it wasn't given, so
other uncommitted work is left alone. Test files are not saved, so the new test stays in place.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

INDEX = "saved.json"

# Exit codes beside D10's 0-3 (0005 D5).
EXIT_PROVED = 0
EXIT_NOT_PROVED = 4  # the test passed without the fix, so it proves nothing
EXIT_UNRESTORED = 5  # a fixed file could not be put back; its copy is kept in the state dir


class LoopError(Exception):
    """Bad arguments or state: reported as a config error (exit code 2)."""


@dataclass
class CheckResult:
    code: int
    test_failed_without_fix: bool
    unrestored: list[str]
    output: str


def _sha(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def _write(path: Path, data: bytes | None) -> None:
    if data is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _inside(root: Path, file: str) -> tuple[str, Path]:
    path = (root / file).resolve()
    if not path.is_relative_to(root.resolve()):
        raise LoopError(f"{file} is outside the repository")
    return str(path.relative_to(root.resolve())), path


def _load(state: Path) -> list[dict]:
    index = state / INDEX
    return json.loads(index.read_text("utf-8")) if index.is_file() else []


def save(state: Path, root: Path, files: list[str]) -> list[str]:
    """Keeps each file's current content as its pre-fix copy. A file saved earlier keeps its
    first copy, so saving again after a partial edit can't lose the original. A file that
    doesn't exist yet is recorded as absent: the fix creates it."""
    if not files:
        raise LoopError("no files to save")
    entries = _load(state)
    known = {e["path"] for e in entries}
    (state / "saved").mkdir(parents=True, exist_ok=True)
    for file in files:
        rel, path = _inside(root, file)
        if rel in known:
            continue
        copy = state / "saved" / str(len(entries))
        data = _read(path)
        _write(copy, data if data is not None else b"")
        entries.append({"path": rel, "copy": str(copy), "existed": data is not None})
        known.add(rel)
    (state / INDEX).write_text(json.dumps(entries, indent=2), "utf-8")
    return [e["path"] for e in entries]


def check(state: Path, root: Path, test: str, timeout: float = 600) -> CheckResult:
    """Runs `test` with the saved pre-fix content in place, then restores the fixed content.

    Proved (exit 0) clears the saved set for the next fix. Not proved (exit 4) keeps it, so the
    session can rewrite the test and check again. Unrestored (exit 5) keeps every copy.
    """
    entries = _load(state)
    if not entries:
        raise LoopError("nothing saved: run `review-personas loop save` before editing")
    paths = {e["path"]: (root / e["path"]) for e in entries}
    fixed = {rel: _read(path) for rel, path in paths.items()}

    # A second copy of the fixed content, so it can be recovered if restoring fails.
    (state / "fixed").mkdir(parents=True, exist_ok=True)
    for i, rel in enumerate(fixed):
        _write(state / "fixed" / str(i), fixed[rel] if fixed[rel] is not None else b"")

    output, failed = "", False
    try:
        for e in entries:
            pre = Path(e["copy"]).read_bytes() if e["existed"] else None
            _write(paths[e["path"]], pre)
        try:
            run = subprocess.run(
                test, shell=True, cwd=root, capture_output=True, text=True, timeout=timeout
            )
            failed, output = run.returncode != 0, (run.stdout + run.stderr)[-4000:]
        except subprocess.TimeoutExpired:
            raise LoopError(f"the test command ran longer than {timeout:g}s") from None
    finally:
        for rel, path in paths.items():
            try:
                _write(path, fixed[rel])
            except OSError:
                pass
        unrestored = [rel for rel, path in paths.items() if _sha(_read(path)) != _sha(fixed[rel])]

    if unrestored:
        return CheckResult(EXIT_UNRESTORED, failed, unrestored, output)
    if not failed:
        return CheckResult(EXIT_NOT_PROVED, failed, [], output)
    (state / INDEX).unlink()
    return CheckResult(EXIT_PROVED, failed, [], output)
