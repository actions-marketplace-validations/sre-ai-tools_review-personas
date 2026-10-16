"""Caller config: `.github/review-personas.yml` merged over built-in defaults (design D6)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .personas import PersonaDef, PersonaError, builtin_personas, custom_personas, string_list

CONFIG_PATH = ".github/review-personas.yml"
DEFAULT_MODEL = "qwen.qwen3-32b-v1:0"
DEFAULT_MAX_DIFF_CHARS = 100_000

# Never sent to a model; callers can add patterns but not remove these (DAT-2, DAT-3).
SENSITIVE = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",
    "id_rsa*",
    "id_ed25519*",
    "id_ecdsa*",
    "*.tfstate",
    "*.tfstate.*",
    ".npmrc",
    ".pypirc",
    "*credentials*.json",
    "*secret*.yml",
    "*secret*.yaml",
)

# Skipped as noise; callers can add (exclude_generated) or remove (include_generated).
GENERATED = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "Gemfile.lock",
    "*.min.js",
    "*.min.css",
    "*.map",
)

TOP_LEVEL_KEYS = {
    "model",
    "max_diff_chars",
    "exclude_sensitive",
    "exclude_generated",
    "include_generated",
    "model_params",
    "prices",
    "personas",
}
PERSONA_KEYS = {"enabled", "model", "model_params", "extra_focus", "paths"}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float


@dataclass(frozen=True)
class Persona:
    """A persona with every setting resolved for this run."""

    id: str
    name: str
    icon: str
    focus: str
    model: str
    paths: tuple[str, ...] | None = None
    model_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    personas: tuple[Persona, ...]
    max_diff_chars: int = DEFAULT_MAX_DIFF_CHARS
    sensitive: tuple[str, ...] = SENSITIVE
    generated: tuple[str, ...] = GENERATED
    prices: dict[str, Price] = field(default_factory=dict)


def _mapping(value: object, where: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: must be a mapping")
    return value


def _str_list(value: object, where: str) -> tuple[str, ...]:
    try:
        return string_list(value, where)
    except PersonaError as e:
        raise ConfigError(str(e)) from e


def parse_persona_ids(value: str) -> list[str] | None:
    """The `personas` input: a JSON array or comma-separated ids; None means all (0003 P2)."""
    if not value.strip():
        return None  # INP-6
    if value.lstrip().startswith("["):  # INP-3
        try:
            items = json.loads(value)
        except ValueError:
            items = None
        if not isinstance(items, list) or not all(isinstance(i, str) and i.strip() for i in items):
            raise ConfigError(  # INP-7, INP-8
                '`personas` must be a JSON array of persona ids like ["aws-architect", "dba"], '
                f"or comma-separated ids like aws-architect,dba; got {value[:200]!r}"
            )
        return [i.strip() for i in items] or None  # INP-4, INP-5
    return [s.strip() for s in value.split(",") if s.strip()] or None  # INP-2


def _prices(raw: object) -> dict[str, Price]:
    out = {}
    for model, p in _mapping(raw, "prices").items():
        p = _mapping(p, f"prices.{model}")
        if set(p) != {"input_per_mtok", "output_per_mtok"} or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 for v in p.values()
        ):
            raise ConfigError(
                f"prices.{model}: needs non-negative numbers `input_per_mtok` and `output_per_mtok`"
            )
        out[model] = Price(float(p["input_per_mtok"]), float(p["output_per_mtok"]))
    return out


def load_settings(
    repo_root: str | Path,
    config_path: str | Path | None = None,
    *,
    model_override: str | None = None,
    personas_override: list[str] | None = None,
) -> Settings:
    """Precedence, highest first: overrides (workflow inputs), the config's per-persona entry,
    the custom persona's frontmatter, top-level config, built-in defaults."""
    repo_root = Path(repo_root)
    path = repo_root / (config_path or CONFIG_PATH)
    raw: dict = {}
    if path.is_file():
        try:
            raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), str(path))
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: invalid YAML: {e}") from e
    unknown = set(raw) - TOP_LEVEL_KEYS
    if unknown:
        raise ConfigError(f"Unknown config keys: {', '.join(sorted(unknown))}")

    try:
        builtins = builtin_personas()
        defs: dict[str, PersonaDef] = {**builtins, **custom_personas(repo_root, set(builtins))}
    except PersonaError as e:
        raise ConfigError(str(e)) from e

    default_model = raw.get("model") or DEFAULT_MODEL
    if not isinstance(default_model, str):
        raise ConfigError("`model` must be a string")
    # Keyed by model ID: params are model-specific, so they follow the model (D6 amendment).
    params_by_model = {
        model_id: _mapping(params, f"model_params.{model_id}")
        for model_id, params in _mapping(raw.get("model_params"), "model_params").items()
    }
    entries = _mapping(raw.get("personas"), "personas")
    unknown_ids = set(entries) - set(defs)
    if unknown_ids:
        raise ConfigError(
            f"Unknown persona ids in config: {', '.join(sorted(unknown_ids))}. "
            f"Known: {', '.join(sorted(defs))}"
        )

    personas = []
    for pid, d in defs.items():
        entry = _mapping(entries.get(pid), f"personas.{pid}")
        bad = set(entry) - PERSONA_KEYS
        if bad:
            raise ConfigError(f"personas.{pid}: unknown keys: {', '.join(sorted(bad))}")
        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(f"personas.{pid}.enabled: must be true or false")
        if not enabled:
            continue
        focus = d.focus
        if entry.get("extra_focus"):
            if not isinstance(entry["extra_focus"], str):
                raise ConfigError(f"personas.{pid}.extra_focus: must be a string")
            focus += "\n\n" + entry["extra_focus"].strip()
        model = model_override or entry.get("model") or d.model or default_model
        if not isinstance(model, str):
            raise ConfigError(f"personas.{pid}.model: must be a string")
        paths = _str_list(entry["paths"], f"personas.{pid}.paths") if "paths" in entry else d.paths
        personas.append(
            Persona(
                id=pid,
                name=d.name,
                icon=d.icon,
                focus=focus,
                model=model,
                paths=paths,
                model_params={
                    **params_by_model.get(model, {}),
                    **_mapping(entry.get("model_params"), f"personas.{pid}.model_params"),
                },
            )
        )

    if personas_override:
        by_id = {p.id: p for p in personas}
        missing = [pid for pid in personas_override if pid not in by_id]
        if missing:
            raise ConfigError(f"Unknown or disabled personas requested: {', '.join(missing)}")
        personas = [by_id[pid] for pid in personas_override]
    if not personas:
        raise ConfigError("No personas enabled")

    max_diff_chars = raw.get("max_diff_chars", DEFAULT_MAX_DIFF_CHARS)
    if (
        not isinstance(max_diff_chars, int)
        or isinstance(max_diff_chars, bool)
        or max_diff_chars < 1
    ):
        raise ConfigError("`max_diff_chars` must be a positive integer")

    include = (
        set(_str_list(raw["include_generated"], "include_generated"))
        if "include_generated" in raw
        else set()
    )
    generated = tuple(p for p in GENERATED if p not in include)
    if "exclude_generated" in raw:
        generated += _str_list(raw["exclude_generated"], "exclude_generated")
    sensitive = SENSITIVE
    if "exclude_sensitive" in raw:
        sensitive += _str_list(raw["exclude_sensitive"], "exclude_sensitive")

    return Settings(
        personas=tuple(personas),
        max_diff_chars=max_diff_chars,
        sensitive=sensitive,
        generated=generated,
        prices=_prices(raw.get("prices")),
    )
