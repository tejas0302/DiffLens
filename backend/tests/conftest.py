import os
import tempfile

# Settings are read at import time, so configure the environment first.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["GITHUB_WEBHOOK_SECRET"] = "test-secret"
os.environ["OPENAI_API_KEY"] = ""
os.environ["MAX_CHANGED_LINES"] = "2000"

import pytest  # noqa: E402

from app.db import Base, engine, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    init_db()
    yield


SAMPLE_FILES = [
    {
        "filename": "src/auth/login.py", "status": "modified", "additions": 6, "deletions": 1,
        "patch": "@@ -10,3 +10,8 @@ def login(user, password):\n"
                 "-    return check(user, password)\n"
                 "+    if attempts(user) > 5:\n"
                 "+        raise TooManyAttempts()\n"
                 "+    ok = check(user, password)\n"
                 "+    print('login', user)\n"
                 "+    record_attempt(user, ok)\n"
                 "+    return ok\n",
    },
    {
        "filename": "src/auth/rate_limit.py", "status": "added", "additions": 4, "deletions": 0,
        "patch": "@@ -0,0 +1,4 @@\n+def attempts(user):\n+    return CACHE.get(user, 0)\n"
                 "+def record_attempt(user, ok):\n+    CACHE[user] = 0 if ok else CACHE.get(user, 0) + 1\n",
    },
    {
        "filename": "requirements.txt", "status": "modified", "additions": 1, "deletions": 0,
        "patch": "@@ -1,2 +1,3 @@\n fastapi\n uvicorn\n+redis==5.0.1\n",
    },
    {"filename": "docs/logo.png", "status": "added", "additions": 0, "deletions": 0},
]
