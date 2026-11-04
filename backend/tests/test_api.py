"""End-to-end tests of the webhook and API, with GitHub and OpenAI mocked."""
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app import main
from app.comment import MARKER
from app.pipeline import process_pull_request

from .conftest import SAMPLE_FILES

SECRET = "test-secret"


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def pr_event(action="opened", sha="abc123", draft=False) -> dict:
    return {
        "action": action,
        "installation": {"id": 42},
        "repository": {"full_name": "tejas/demo"},
        "pull_request": {
            "number": 7, "title": "Add login rate limiting", "body": "Blocks brute force.",
            "draft": draft, "head": {"sha": sha}, "user": {"login": "tejas"},
            "html_url": "https://github.com/tejas/demo/pull/7",
        },
    }


def post_event(client, payload, event="pull_request", signature=None):
    body = json.dumps(payload).encode()
    return client.post("/webhook", content=body, headers={
        "X-GitHub-Event": event,
        "X-Hub-Signature-256": signature if signature is not None else sign(body),
        "Content-Type": "application/json",
    })


def test_rejects_bad_signature():
    with TestClient(main.app) as client:
        assert post_event(client, pr_event(), signature="sha256=wrong").status_code == 401


def test_ping_and_ignored_events():
    with TestClient(main.app) as client:
        assert post_event(client, {"zen": "hi"}, event="ping").json()["pong"] is True
        assert post_event(client, {}, event="issues").json()["ignored"] == "issues"
        assert post_event(client, pr_event(action="closed")).json()["ignored"] == "closed"
        assert post_event(client, pr_event(draft=True)).json()["ignored"] == "opened"


def test_full_flow_and_idempotency(monkeypatch):
    posted: list[str] = []

    def fake_process(**kwargs):
        process_pull_request(**kwargs, fetch_files=lambda: SAMPLE_FILES, post_comment=posted.append)

    monkeypatch.setattr(main, "process_pull_request", fake_process)

    with TestClient(main.app) as client:
        r = post_event(client, pr_event())
        assert r.status_code == 200
        review_id = r.json()["review_id"]

        # Same commit delivered again -> no second review.
        assert post_event(client, pr_event()).json()["duplicate"] is True

        detail = client.get(f"/api/reviews/{review_id}").json()
        assert detail["status"] == "done"
        assert detail["model"] == "fallback"           # no API key in tests
        assert detail["stats"]["files"] == 4
        assert any(r["kind"] == "security" for r in detail["risks"])
        assert len(detail["files"]) == 4

        listing = client.get("/api/reviews").json()
        assert listing[0]["id"] == review_id and listing[0]["high_risk_count"] >= 1

        assert len(posted) == 1 and MARKER in posted[0] and f"/reviews/{review_id}" in posted[0]

        # A new commit on the same PR -> a new review.
        assert "review_id" in post_event(client, pr_event(action="synchronize", sha="def456")).json()


def test_large_pr_is_skipped(monkeypatch):
    big = [{"filename": "big.py", "status": "modified", "additions": 3000, "deletions": 0, "patch": ""}]
    posted: list[str] = []
    monkeypatch.setattr(main, "process_pull_request",
                        lambda **kw: process_pull_request(**kw, fetch_files=lambda: big, post_comment=posted.append))
    with TestClient(main.app) as client:
        review_id = post_event(client, pr_event(sha="big1")).json()["review_id"]
        assert client.get(f"/api/reviews/{review_id}").json()["status"] == "skipped"
        assert "limit" in posted[0]


def test_github_failure_marks_review_failed(monkeypatch):
    def boom():
        raise RuntimeError("GitHub is down")
    monkeypatch.setattr(main, "process_pull_request",
                        lambda **kw: process_pull_request(**kw, fetch_files=boom, post_comment=lambda t: None))
    with TestClient(main.app) as client:
        review_id = post_event(client, pr_event(sha="fail1")).json()["review_id"]
        detail = client.get(f"/api/reviews/{review_id}").json()
        assert detail["status"] == "failed" and "GitHub is down" in detail["error"]


def test_404():
    with TestClient(main.app) as client:
        assert client.get("/api/reviews/999").status_code == 404
