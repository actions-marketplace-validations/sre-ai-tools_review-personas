"""Persona definitions: Markdown files with a YAML frontmatter header (design D2)."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml

CUSTOM_DIR = ".github/review-personas/personas"
FRONTMATTER_KEYS = {"name", "icon", "paths", "model"}


class PersonaError(ValueError):
    pass


@dataclass(frozen=True)
class PersonaDef:
    id: str
    name: str
    focus: str
    icon: str = ""
    paths: tuple[str, ...] | None = None
    model: str | None = None
    builtin: bool = False


def string_list(value: object, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise PersonaError(f"{where}: must be a list of non-empty strings")
    return tuple(value)


def parse_persona(pid: str, text: str, *, source: str, builtin: bool = False) -> PersonaDef:
    if not text.startswith("---\n"):
        raise PersonaError(f"{source}: must start with a '---' frontmatter header")
    end = text.find("\n---", 4)
    if end == -1:
        raise PersonaError(f"{source}: frontmatter header is not closed with '---'")
    try:
        meta = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError as e:
        raise PersonaError(f"{source}: invalid frontmatter YAML: {e}") from e
    if not isinstance(meta, dict):
        raise PersonaError(f"{source}: frontmatter must be a mapping")
    unknown = set(meta) - FRONTMATTER_KEYS
    if unknown:
        raise PersonaError(f"{source}: unknown frontmatter keys: {', '.join(sorted(unknown))}")
    if not isinstance(meta.get("name"), str) or not meta["name"].strip():
        raise PersonaError(f"{source}: frontmatter needs a `name`")
    focus = text[end + 4 :].strip()
    if not focus:
        raise PersonaError(f"{source}: the persona body (its focus) is empty")
    model = meta.get("model")
    if model is not None and not isinstance(model, str):
        raise PersonaError(f"{source}: `model` must be a string")
    return PersonaDef(
        id=pid,
        name=meta["name"].strip(),
        focus=focus,
        icon=str(meta.get("icon") or ""),
        paths=string_list(meta["paths"], f"{source}: `paths`") if "paths" in meta else None,
        model=model,
        builtin=builtin,
    )


def builtin_personas() -> dict[str, PersonaDef]:
    out = {}
    for entry in sorted(
        resources.files("review_personas").joinpath("personas").iterdir(), key=lambda e: e.name
    ):
        if entry.name.endswith(".md"):
            pid = entry.name[:-3]
            out[pid] = parse_persona(
                pid, entry.read_text(encoding="utf-8"), source=f"built-in {pid}", builtin=True
            )
    return out


def custom_personas(repo_root: Path, builtin_ids: set[str]) -> dict[str, PersonaDef]:
    out = {}
    folder = repo_root / CUSTOM_DIR
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.md")):
        pid = path.stem
        source = f"{CUSTOM_DIR}/{path.name}"
        if pid in builtin_ids:
            raise PersonaError(
                f"{source}: '{pid}' is a built-in persona id. Rename the file, or change the "
                f"built-in through `personas.{pid}.extra_focus` in the config."
            )
        out[pid] = parse_persona(pid, path.read_text(encoding="utf-8"), source=source)
    return out
