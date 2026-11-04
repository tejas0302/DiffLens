"""Everything that talks to GitHub.

How a GitHub App authenticates (common interview question):
1. The app has a private key. We sign a short-lived JWT (10 min max) with it.
   That JWT proves "I am app #123" but can't touch any repo yet.
2. We exchange the JWT for an *installation token* for the specific account
   that installed the app. That token (1 hour) can read PRs / write comments
   only on the repos that account granted us.
Least privilege: we never hold a user's personal token.
"""
import hashlib
import hmac
import time

import httpx
import jwt

from .config import settings

API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def verify_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    """Check the webhook really came from GitHub.

    GitHub sends X-Hub-Signature-256: sha256=<HMAC of the raw body using our
    secret>. We recompute it and compare with compare_digest, which takes the
    same time whether the strings match early or late (prevents timing attacks).
    """
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def app_jwt() -> str:
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": settings.github_app_id}
    return jwt.encode(payload, settings.github_private_key, algorithm="RS256")


def installation_token(installation_id: int) -> str:
    r = httpx.post(
        f"{API}/app/installations/{installation_id}/access_tokens",
        headers={**HEADERS, "Authorization": f"Bearer {app_jwt()}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["token"]


def list_pr_files(token: str, repo: str, pr_number: int) -> list[dict]:
    """GitHub paginates at most 100 files per page (and caps at 3000 files)."""
    files: list[dict] = []
    page = 1
    with httpx.Client(headers={**HEADERS, "Authorization": f"Bearer {token}"}, timeout=20) as c:
        while True:
            r = c.get(f"{API}/repos/{repo}/pulls/{pr_number}/files",
                      params={"per_page": 100, "page": page})
            r.raise_for_status()
            batch = r.json()
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    return files


def upsert_comment(token: str, repo: str, pr_number: int, body: str, marker: str) -> None:
    """Edit our previous comment if there is one, otherwise create it.

    Without this, every push to the PR would add another bot comment (spam).
    We find our own comment by a hidden HTML marker inside it.
    """
    with httpx.Client(headers={**HEADERS, "Authorization": f"Bearer {token}"}, timeout=20) as c:
        r = c.get(f"{API}/repos/{repo}/issues/{pr_number}/comments", params={"per_page": 100})
        r.raise_for_status()
        existing = next((cm for cm in r.json() if marker in (cm.get("body") or "")), None)
        if existing:
            c.patch(f"{API}/repos/{repo}/issues/comments/{existing['id']}", json={"body": body}).raise_for_status()
        else:
            # PR comments live on the "issues" API: every PR is also an issue.
            c.post(f"{API}/repos/{repo}/issues/{pr_number}/comments", json={"body": body}).raise_for_status()
