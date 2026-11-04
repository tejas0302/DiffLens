"""Database layer (SQLAlchemy 2.x).

Same code runs on SQLite (local dev, tests) and Postgres (production);
only DATABASE_URL changes.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, DateTime, Integer, String, Text, UniqueConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings


def _make_engine(url: str):
    # Some hosts hand out "postgres://" URLs; SQLAlchemy wants "postgresql://".
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    kwargs = {}
    if url.startswith("sqlite"):
        # Needed because FastAPI background tasks run on a different thread.
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, pool_pre_ping=True, **kwargs)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Review(Base):
    """One analysis of one commit of one pull request."""

    __tablename__ = "reviews"
    # Idempotency: GitHub can deliver the same event twice, and we only want
    # one review per (repo, PR, commit).
    __table_args__ = (UniqueConstraint("repo", "pr_number", "head_sha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo: Mapped[str] = mapped_column(String(255), index=True)        # "owner/name"
    pr_number: Mapped[int] = mapped_column(Integer)
    head_sha: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(500), default="")
    author: Mapped[str] = mapped_column(String(255), default="")
    pr_url: Mapped[str] = mapped_column(String(500), default="")
    # pending -> done | skipped | failed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    summary: Mapped[str] = mapped_column(Text, default="")
    groups: Mapped[list] = mapped_column(JSON, default=list)      # logical change groups
    risks: Mapped[list] = mapped_column(JSON, default=list)       # risk flags
    files: Mapped[list] = mapped_column(JSON, default=list)       # per-file patches for the UI
    stats: Mapped[dict] = mapped_column(JSON, default=dict)       # additions, deletions, file count
    model: Mapped[str] = mapped_column(String(100), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def init_db() -> None:
    Base.metadata.create_all(engine)
