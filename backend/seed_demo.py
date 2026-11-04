"""Create a realistic demo review without GitHub, so you can see the UI locally.

Run from backend/:  python seed_demo.py
Uses the real pipeline (rules + LLM if OPENAI_API_KEY is set, fallback otherwise).
"""
from app.db import init_db
from app.pipeline import create_pending_review, process_pull_request

DEMO_FILES = [
    {
        "filename": "src/auth/login.py", "status": "modified", "additions": 9, "deletions": 2,
        "patch": (
            "@@ -1,4 +1,5 @@\n import hashlib\n+from .rate_limit import attempts, record_attempt\n from .db import users\n \n"
            "@@ -18,6 +19,14 @@ def login(username: str, password: str) -> bool:\n"
            "     user = users.get(username)\n"
            "-    if not user:\n"
            "-        return False\n"
            "+    if attempts(username) >= 5:\n"
            "+        raise PermissionError(\"Too many attempts, try again later\")\n"
            "+    ok = user is not None and verify(user, password)\n"
            "+    print(\"login attempt\", username, ok)\n"
            "+    record_attempt(username, ok)\n"
            "+    return ok\n"
            "+\n"
            "+\n"
            " def verify(user, password):\n"
        ),
    },
    {
        "filename": "src/auth/rate_limit.py", "status": "added", "additions": 12, "deletions": 0,
        "patch": (
            "@@ -0,0 +1,12 @@\n"
            "+import time\n+\n"
            "+_FAILED: dict[str, list[float]] = {}\n"
            "+WINDOW_SECONDS = 15 * 60\n+\n"
            "+def attempts(username: str) -> int:\n"
            "+    now = time.time()\n"
            "+    recent = [t for t in _FAILED.get(username, []) if now - t < WINDOW_SECONDS]\n"
            "+    _FAILED[username] = recent\n"
            "+    return len(recent)\n+\n"
            "+def record_attempt(username: str, ok: bool) -> None:\n"
        ),
    },
    {
        "filename": "src/api/routes.py", "status": "modified", "additions": 4, "deletions": 1,
        "patch": (
            "@@ -40,7 +40,10 @@ def login_route(req):\n"
            "-    ok = login(req.json[\"username\"], req.json[\"password\"])\n"
            "+    try:\n"
            "+        ok = login(req.json[\"username\"], req.json[\"password\"])\n"
            "+    except PermissionError as e:\n"
            "+        return {\"error\": str(e)}, 429\n"
            "     return {\"ok\": ok}, 200 if ok else 401\n"
        ),
    },
    {
        "filename": "requirements.txt", "status": "modified", "additions": 1, "deletions": 0,
        "patch": "@@ -3,2 +3,3 @@\n flask==3.0.0\n bcrypt==4.1.2\n+redis==5.0.1\n",
    },
]

if __name__ == "__main__":
    init_db()
    review_id = create_pending_review(
        repo="demo/shop-api", pr_number=42, head_sha="9f3c2ab7e1d04c55",
        title="Rate-limit failed logins", author="tejas",
        pr_url="https://github.com/",
    )
    if review_id is None:
        print("Demo review already exists.")
    else:
        process_pull_request(
            review_id=review_id, installation_id=0, repo="demo/shop-api", pr_number=42,
            title="Rate-limit failed logins",
            body="Locks an account for 15 minutes after 5 failed logins.",
            fetch_files=lambda: DEMO_FILES,
            post_comment=lambda text: print("---- PR comment that would be posted ----\n" + text),
        )
        print(f"\nOpen http://localhost:3000/reviews/{review_id}")
