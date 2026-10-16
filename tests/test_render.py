from review_personas.config import Persona, Price
from review_personas.filtering import NotReviewed
from review_personas.render import MARKER, comment, cost_text, escape, job_summary
from review_personas.reply import Finding, Verdict
from review_personas.result import PersonaResult, Usage


def persona(pid, name, icon, model="m1"):
    return Persona(id=pid, name=name, icon=icon, focus="f", model=model)


AWS = persona("aws-architect", "AWS architect", "☁️")
APP = persona("app-developer", "App developer", "🧑‍💻")
UI = persona("ui-developer", "UI developer", "🎨")
DBA = persona("dba", "DBA", "🗄️", model="m2")
SEC = persona("security", "Security", "🔐")


def results():
    return [
        PersonaResult(
            AWS,
            Verdict(
                True,
                "IAM scoped well; add retries.",
                8,
                (Finding("medium", "Set a timeout below the 29s limit.", "infra/lambda.tf", 12),),
            ),
            usage=Usage(5000, 200),
        ),
        PersonaResult(
            APP,
            Verdict(
                True, "Null user not handled.", 7, (Finding("high", "Return 404.", "api/u.py"),)
            ),
            usage=Usage(5000, 200),
        ),
        PersonaResult(UI, Verdict(False, "No UI changes."), usage=Usage(2400, 50)),
        PersonaResult(DBA, skipped_by_paths=True),
        PersonaResult(SEC, error="ThrottlingException: rate exceeded", usage=Usage(0, 0)),
    ]


# COM-1, COM-3, COM-4, SCO-1, SCO-3, CI-5
def test_comment_layout():
    body = comment(
        results(),
        not_reviewed=[
            NotReviewed(".env", "sensitive"),
            NotReviewed("yarn.lock", "generated/binary"),
        ],
        prices={"m1": Price(4, 20)},
        reviewed="commit abc1234",
    )
    assert body.splitlines()[0] == MARKER
    assert "## 🧩 Persona review: 7.5/10 (advisory)" in body
    assert "| ☁️ AWS architect | 8 | IAM scoped well; add retries. |" in body
    assert "| 🎨 UI developer | – | Not relevant |" in body
    assert "| 🗄️ DBA | – | Not relevant: no matching files |" in body
    assert "| 🔐 Security | ⚠️ | Review failed: ThrottlingException: rate exceeded |" in body
    assert "- 🟠 `infra/lambda.tf:12` Set a timeout below the 29s limit." in body
    assert "- 🔴 `api/u.py` Return 404." in body
    assert "**🎨 UI developer**" not in body  # not-relevant personas have no findings section
    assert "Not reviewed: `.env` (sensitive), `yarn.lock` (generated/binary)." in body
    assert "Reviewed commit abc1234." in body
    assert "Tokens: 12.4k in / 450 out, est. $0.06." in body


def test_no_score_and_no_tokens_locally():
    r = [PersonaResult(UI, Verdict(False, "x"))]
    body = comment(r, not_reviewed=[], prices={}, reviewed="feature vs main")
    assert "no score (no relevant reviews)" in body and "Tokens" not in body


# REV-5: model output cannot render links, images, HTML, mentions or break the table
def test_escape():
    out = escape("Ping @alice | see [x](http://evil) ![i](https://e/i.png) <img src=x> **b**")
    assert "@​alice" in out
    assert "\\|" in out and "\\[x\\]" in out and "\\!\\[i\\]" in out
    assert "&lt;img src=x&gt;" in out and "\\*\\*b\\*\\*" in out
    assert "http://" not in out and "https://" not in out


def test_cost_partial_and_none():
    r = results()
    assert cost_text(r, {}) is None
    assert cost_text(r, {"m1": Price(4, 20), "m2": Price(1, 1)}) == "$0.06"
    r[3] = PersonaResult(DBA, Verdict(True, "s", 5), usage=Usage(1000, 10))
    assert "partial" in cost_text(r, {"m1": Price(4, 20)})


def test_job_summary():
    s = job_summary(results(), {"m1": Price(4, 20)})
    assert "| ☁️ AWS architect | `m1` | 5000 | 200 | $0.0240 | 0.0 |" in s
    assert "| **Total** | | 12400 | 450 | $0.06 | |" in s
