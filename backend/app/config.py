"""All settings come from environment variables, so secrets never live in code.

Locally you put them in backend/.env; in production you set them in the host's
dashboard (Railway / Fly / Render).
"""
import os
from dataclasses import dataclass


def _load_dotenv(path: str = ".env") -> None:
    """Tiny .env loader so we don't need an extra dependency."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    github_app_id: str = os.getenv("GITHUB_APP_ID", "")
    # The private key is multi-line; in .env we store it with literal "\n".
    github_private_key: str = os.getenv("GITHUB_PRIVATE_KEY", "").replace("\\n", "\n")
    github_webhook_secret: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./difflens.db")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    # Guardrail: PRs bigger than this are skipped with a friendly message.
    max_changed_lines: int = int(os.getenv("MAX_CHANGED_LINES", "2000"))
    # Guardrail: each file's patch is truncated before it is sent to the LLM.
    max_patch_chars_per_file: int = int(os.getenv("MAX_PATCH_CHARS_PER_FILE", "4000"))


settings = Settings()
