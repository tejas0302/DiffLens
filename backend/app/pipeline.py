"""The end-to-end job that runs for every PR event.

fetch files -> parse -> size guard -> rule risks -> LLM grouping -> save -> comment
"""
import logging

from sqlalchemy import select

from . import github
from .analyzer import analyze
from .comment import MARKER, render_comment, render_skipped
from .config import settings
from .db import Review, SessionLocal
from .diff_parser import diff_stats, parse_files
from .risk import find_risks

log = logging.getLogger("difflens")


def process_pull_request(
    *, review_id: int, installation_id: int, repo: str, pr_number: int,
    title: str, body: str,
    fetch_files=None, post_comment=None,
) -> None:
    """fetch_files / post_comment can be injected so tests don't call GitHub."""
    token = None
    if fetch_files is None or post_comment is None:
        token = github.installation_token(installation_id)
    fetch_files = fetch_files or (lambda: github.list_pr_files(token, repo, pr_number))
    post_comment = post_comment or (lambda text: github.upsert_comment(token, repo, pr_number, text, MARKER))

    with SessionLocal() as db:
        review = db.get(Review, review_id)
        try:
            files = parse_files(fetch_files())
            stats = diff_stats(files)
            review.stats = stats
            review.files = [f.to_dict() for f in files]

            changed = stats["additions"] + stats["deletions"]
            if changed > settings.max_changed_lines:
                review.status = "skipped"
                review.summary = f"Skipped: {changed} changed lines exceeds limit."
                db.commit()
                post_comment(render_skipped(changed, settings.max_changed_lines))
                return

            rule_risks = find_risks(files)
            result = analyze(title, body, files)

            review.summary = result["summary"]
            review.groups = result["groups"]
            review.risks = rule_risks + result["llm_risks"]
            review.model = result["model"]
            review.latency_ms = result["latency_ms"]
            review.status = "done"
            db.commit()

            post_comment(render_comment(
                {"id": review.id, "summary": review.summary, "groups": review.groups,
                 "risks": review.risks, "stats": stats},
                settings.frontend_url,
            ))
        except Exception as exc:
            log.exception("review %s failed", review_id)
            review.status = "failed"
            review.error = f"{type(exc).__name__}: {exc}"[:2000]
            db.commit()


def create_pending_review(*, repo: str, pr_number: int, head_sha: str,
                          title: str, author: str, pr_url: str) -> int | None:
    """Insert a pending row. Returns None if this exact commit was already reviewed."""
    with SessionLocal() as db:
        exists = db.scalar(select(Review.id).where(
            Review.repo == repo, Review.pr_number == pr_number, Review.head_sha == head_sha))
        if exists:
            return None
        review = Review(repo=repo, pr_number=pr_number, head_sha=head_sha,
                        title=title, author=author, pr_url=pr_url)
        db.add(review)
        db.commit()
        return review.id
