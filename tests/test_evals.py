"""The eval suite itself must be well-formed and gradeable without calling Bedrock."""

import importlib.util
import sys
from pathlib import Path

from review_personas.llm import Completion
from review_personas.personas import builtin_personas
from review_personas.result import Usage

spec = importlib.util.spec_from_file_location(
    "evals_run", Path(__file__).resolve().parents[1] / "evals/run.py"
)
evals = importlib.util.module_from_spec(spec)
sys.modules["evals_run"] = evals
spec.loader.exec_module(evals)


def test_cases_are_well_formed():
    cases = evals.load_cases()
    assert len(cases) == 12
    ids = set(builtin_personas())
    for case in cases:
        assert case.files, case.name
        for key, exp in case.expect.items():
            assert key in evals.CASE_KEYS or (key in ids and "relevant" in exp), (case.name, key)


class OracleLLM:
    """Answers exactly what each case expects, so every bar should pass."""

    def __init__(self, cases):
        self.expect = {c.title: c.expect for c in cases}
        self.names = {p.name: pid for pid, p in builtin_personas().items()}

    def complete(self, *, model, system, messages, model_params):
        if system == evals.JUDGE_SYSTEM:
            return Completion("yes", "end_turn", Usage())
        name = system.split("You are the ", 1)[1].split(" on a", 1)[0]
        title = messages[0]["text"].split("<pr_title>", 1)[1].split("</pr_title>", 1)[0]
        exp = self.expect[title].get(self.names[name], {"relevant": False})
        if not exp["relevant"]:
            return Completion('{"relevant": false, "summary": "n/a"}', "end_turn", Usage())
        text = '{"relevant": true, "score": 4, "summary": "Issue found.", "findings": []}'
        return Completion(text, "end_turn", Usage(10, 5))


def test_oracle_passes_every_bar():
    cases = evals.load_cases()
    report, ok = evals.run_evals(OracleLLM(cases), cases=cases)
    assert ok, report
    assert "| sensitive | 3/3 | 100% |" in report
