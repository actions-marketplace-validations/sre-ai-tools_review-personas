"""Guards on the CI packaging files (D11) - cheap checks that catch regressions before a release."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return yaml.safe_load((ROOT / path).read_text())


def test_action_passes_inputs_through_env_only():
    action = load("action.yml")
    for step in action["runs"]["steps"]:
        # Interpolating ${{ }} into a run script allows shell injection.
        assert "${{" not in step.get("run", ""), step


def test_reusable_workflow_contract():
    wf = load(".github/workflows/review.yml")
    call = wf[True]["workflow_call"]  # PyYAML reads the `on` key as True
    assert call["inputs"]["aws-role-arn"]["required"] is True
    job = wf["jobs"]["review"]
    assert job["permissions"] == {
        "contents": "read",
        "pull-requests": "write",
        "id-token": "write",
    }
    checkout = job["steps"][0]
    assert checkout["with"]["fetch-depth"] == 0
    assert "head.sha" in checkout["with"]["ref"]
    assert re.fullmatch(r"sre-ai-tools/review-personas@\S+", job["steps"][-1]["uses"])


def test_caller_example_uses_pull_request_not_target():
    wf = load("examples/caller-workflow.yml")
    assert "pull_request" in wf[True] and "pull_request_target" not in wf[True]
    assert wf["concurrency"]["cancel-in-progress"] is True


def test_examples_are_valid_config(tmp_path):
    from review_personas.config import load_settings

    (tmp_path / ".github/review-personas/personas").mkdir(parents=True)
    (tmp_path / ".github/review-personas.yml").write_text(
        (ROOT / "examples/review-personas.yml").read_text()
    )
    (tmp_path / ".github/review-personas/personas/security.md").write_text(
        (ROOT / "examples/security.md").read_text()
    )
    ids = [p.id for p in load_settings(tmp_path).personas]
    assert ids == ["app-developer", "aws-architect", "dba", "ui-developer", "security"]


def test_release_rewrites_review_workflow_ref():
    release = (ROOT / ".github/workflows/release.yml").read_text()
    assert "uses: sre-ai-tools/review-personas)@" in release
    assert (ROOT / ".github/workflows/review.yml").read_text().count(
        "uses: sre-ai-tools/review-personas@"
    ) == 1
