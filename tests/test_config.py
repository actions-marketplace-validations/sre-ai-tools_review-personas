import pytest

from review_personas.config import DEFAULT_MODEL, SENSITIVE, ConfigError, load_settings
from review_personas.personas import PersonaError, builtin_personas, parse_persona

BUILTINS = ["app-developer", "aws-architect", "dba", "ui-developer"]


def repo(tmp_path, config=None, custom=None):
    if config is not None:
        (tmp_path / ".github").mkdir(exist_ok=True)
        (tmp_path / ".github/review-personas.yml").write_text(config)
    for name, text in (custom or {}).items():
        d = tmp_path / ".github/review-personas/personas"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(text)
    return tmp_path


SECURITY = "---\nname: Security engineer\nicon: 🔐\nmodel: m-sec\n---\n- Authz checks\n"


# PER-1, PER-2
def test_builtins_parse():
    defs = builtin_personas()
    assert sorted(defs) == BUILTINS
    assert all(d.name and d.focus and d.builtin and d.paths is None for d in defs.values())


# PER-3, PER-4: no config means every built-in on the default model
def test_no_config(tmp_path):
    s = load_settings(tmp_path)
    assert [p.id for p in s.personas] == BUILTINS
    assert {p.model for p in s.personas} == {DEFAULT_MODEL}
    assert s.sensitive == SENSITIVE and s.prices == {}


# PER-3 opt-out, PER-4 models, PER-5 extra focus, PER-6 custom personas
def test_overrides_and_custom(tmp_path):
    s = load_settings(
        repo(
            tmp_path,
            """
model: m-default
model_params:
  m-dba: {a: 1}
  m-default: {c: 3}
personas:
  aws-architect: {enabled: false}
  dba: {model: m-dba, extra_focus: "Postgres 16 only.", model_params: {b: 2}}
  ui-developer: {paths: ["web/*"]}
""",
            {"security": SECURITY},
        )
    )
    by = {p.id: p for p in s.personas}
    assert sorted(by) == ["app-developer", "dba", "security", "ui-developer"]
    assert by["app-developer"].model == "m-default"
    assert by["dba"].model == "m-dba" and by["dba"].focus.endswith("Postgres 16 only.")
    # D6 amendment: params follow the model each persona actually uses
    assert by["dba"].model_params == {"a": 1, "b": 2}
    assert by["app-developer"].model_params == {"c": 3}
    assert by["security"].model_params == {}  # m-sec has no entry
    assert by["ui-developer"].paths == ("web/*",)
    assert by["security"].model == "m-sec" and by["security"].icon == "🔐"


def test_precedence_override_beats_everything(tmp_path):
    s = load_settings(
        repo(tmp_path, "personas:\n  dba: {model: m-dba}\n", {"security": SECURITY}),
        model_override="m-cli",
        personas_override=["security", "dba"],
    )
    assert [(p.id, p.model) for p in s.personas] == [("security", "m-cli"), ("dba", "m-cli")]


# PER-7
@pytest.mark.parametrize(
    "config, match",
    [
        ("modle: x\n", "Unknown config keys: modle"),
        ("personas:\n  dba: {wieght: 2}\n", "unknown keys: wieght"),
        ("personas:\n  dbaa: {}\n", "Unknown persona ids in config: dbaa"),
        ("personas:\n  dba: {enabled: 'no'}\n", "must be true or false"),
        ("personas:\n  dba: {paths: '*.sql'}\n", "list of non-empty strings"),
        ("max_diff_chars: -1\n", "positive integer"),
        ("model_params: {effort: low}\n", "model_params.effort: must be a mapping"),
        ("prices:\n  m: {input_per_mtok: 1}\n", "prices.m"),
        ("personas: [dba]\n", "must be a mapping"),
        ("model: [\n", "invalid YAML"),
    ],
)
def test_config_errors(tmp_path, config, match):
    with pytest.raises(ConfigError, match=match):
        load_settings(repo(tmp_path, config))


def test_custom_reusing_builtin_id_is_error(tmp_path):
    with pytest.raises(ConfigError, match="built-in persona id"):
        load_settings(repo(tmp_path, custom={"dba": SECURITY}))


def test_override_unknown_or_disabled(tmp_path):
    path = repo(tmp_path, "personas:\n  dba: {enabled: false}\n")
    with pytest.raises(ConfigError, match="dba"):
        load_settings(path, personas_override=["dba"])


@pytest.mark.parametrize(
    "text, match",
    [
        ("no header", "must start"),
        ("---\nname: X\n", "not closed"),
        ("---\nicon: x\n---\nfocus", "needs a `name`"),
        ("---\nname: X\n---\n  \n", "body"),
        ("---\nname: X\ncolour: red\n---\nfocus", "unknown frontmatter keys: colour"),
    ],
)
def test_persona_file_errors(text, match):
    with pytest.raises(PersonaError, match=match):
        parse_persona("x", text, source="x.md")


# DAT-2, DAT-3: callers add to the deny list but cannot remove; generated list is adjustable
def test_lists(tmp_path):
    s = load_settings(
        repo(
            tmp_path,
            """
exclude_sensitive: ["config/prod/*"]
exclude_generated: ["*.pb.go"]
include_generated: ["go.sum"]
prices:
  m: {input_per_mtok: 4, output_per_mtok: 20}
""",
        )
    )
    assert s.sensitive[: len(SENSITIVE)] == SENSITIVE and s.sensitive[-1] == "config/prod/*"
    assert "go.sum" not in s.generated and "*.pb.go" in s.generated
    assert s.prices["m"].output_per_mtok == 20.0


def test_model_params_follow_workflow_model_override(tmp_path):
    s = load_settings(
        repo(tmp_path, "model_params:\n  m-cli: {x: 1}\n  m-other: {y: 2}\n"),
        model_override="m-cli",
    )
    assert {p.id: p.model_params for p in s.personas}["dba"] == {"x": 1}
