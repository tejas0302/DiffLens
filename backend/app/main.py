"""HTTP layer: the webhook GitHub calls, and a small read API for the frontend."""
import json
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .config import settings
from .db import Review, SessionLocal, init_db
from .github import verify_signature
from .pipeline import create_pending_review, process_pull_request

logging.basicConfig(level=logging.INFO)

# Only these PR actions mean "there is new code to review".
HANDLED_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="DiffLens", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks):
    # 1. Authenticate: read the RAW bytes (the signature is over exact bytes,
    #    re-serialising JSON would change them).
    body = await request.body()
    if not verify_signature(body, request.headers.get("X-Hub-Signature-256"), settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="bad signature")

    # 2. Filter: ignore events we don't care about, but still return 200 so
    #    GitHub doesn't mark the delivery as failed.
    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return {"ok": True, "pong": True}
    if event != "pull_request":
        return {"ok": True, "ignored": event}

    payload = json.loads(body)
    action = payload.get("action")
    pr = payload["pull_request"]
    if action not in HANDLED_ACTIONS or pr.get("draft"):
        return {"ok": True, "ignored": action}

    repo = payload["repository"]["full_name"]

    # 3. Idempotency: one review per commit, even if GitHub redelivers.
    review_id = create_pending_review(
        repo=repo, pr_number=pr["number"], head_sha=pr["head"]["sha"],
        title=pr.get("title", ""), author=pr.get("user", {}).get("login", ""),
        pr_url=pr.get("html_url", ""),
    )
    if review_id is None:
        return {"ok": True, "duplicate": True}

    # 4. Respond fast, work later. GitHub times out webhooks after 10 seconds;
    #    an LLM call can take longer, so the heavy work runs after we reply.
    background.add_task(
        process_pull_request,
        review_id=review_id, installation_id=payload["installation"]["id"],
        repo=repo, pr_number=pr["number"],
        title=pr.get("title", ""), body=pr.get("body") or "",
    )
    return {"ok": True, "review_id": review_id}


def _summary_row(r: Review) -> dict:
    return {
        "id": r.id, "repo": r.repo, "pr_number": r.pr_number, "title": r.title,
        "author": r.author, "status": r.status, "stats": r.stats,
        "risk_count": len(r.risks or []),
        "high_risk_count": sum(1 for x in (r.risks or []) if x.get("severity") == "high"),
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@app.get("/api/reviews")
def list_reviews(limit: int = 50):
    with SessionLocal() as db:
        rows = db.scalars(select(Review).order_by(Review.id.desc()).limit(min(limit, 200))).all()
        return [_summary_row(r) for r in rows]


@app.get("/api/reviews/{review_id}")
def get_review(review_id: int):
    with SessionLocal() as db:
        r = db.get(Review, review_id)
        if not r:
            raise HTTPException(status_code=404, detail="not found")
        return {
            **_summary_row(r), "head_sha": r.head_sha, "pr_url": r.pr_url,
            "summary": r.summary, "groups": r.groups, "risks": r.risks,
            "files": r.files, "model": r.model, "latency_ms": r.latency_ms, "error": r.error,
        }
