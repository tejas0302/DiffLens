"""LLM step: group the diff into logical changes and add judgment-based risks.

Three ideas worth knowing for interviews:
1. Structured output: we give the model a JSON schema, so we get parseable
   JSON back instead of free text we would have to regex.
2. Validation: we never trust the model blindly. Every file must land in
   exactly one group; we repair what we can and fall back if we can't.
3. Fallback: if the API is down or the output is unusable, we still return a
   useful (if dumber) result grouped by directory. The product never breaks
   because of the model.
"""
import json
import time
from collections import defaultdict

from .config import settings
from .diff_parser import FileDiff

SYSTEM_PROMPT = """You are a senior engineer helping a teammate review a pull request.
Group the changed files into a small number (1-6) of LOGICAL changes, i.e. what the
author was trying to do (e.g. "Add rate limiting to the login endpoint", "Update tests",
"Bump dependencies"), not one group per file.

Rules:
- Every file path you are given must appear in exactly one group. Use paths exactly as given.
- Order groups so a reviewer should read them in that order (core logic first, tests/config last).
- Each group's "summary" is 1-2 plain sentences on what changed and why it matters.
- "risks" are concrete things a reviewer should check (a missing null check, an unhandled
  error, a behaviour change for existing callers). Only report risks you can point to in
  the diff. If there are none, return an empty list. Do not invent problems.
- "summary" at the top level is 1-2 sentences describing the whole PR."""

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "groups", "risks"],
    "properties": {
        "summary": {"type": "string"},
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "summary", "files"],
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "files": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "path", "message"],
                "properties": {
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "path": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
        },
    },
}


def build_user_prompt(title: str, body: str, files: list[FileDiff]) -> str:
    """Pack the PR into the prompt, truncating each patch to control cost."""
    parts = [f"PR title: {title}", f"PR description: {(body or '(none)')[:1500]}", "", "Changed files:"]
    limit = settings.max_patch_chars_per_file
    for f in files:
        patch = f.patch or "(binary or too large, no diff available)"
        if len(patch) > limit:
            patch = patch[:limit] + "\n... (truncated)"
        parts.append(f"\n### {f.path} [{f.status}, +{f.additions} -{f.deletions}]\n{patch}")
    return "\n".join(parts)


def fallback_groups(files: list[FileDiff]) -> list[dict]:
    """Deterministic grouping by top-level directory. Used when the LLM fails."""
    buckets: dict[str, list[str]] = defaultdict(list)
    for f in files:
        top = f.path.split("/", 1)[0] if "/" in f.path else "(root)"
        buckets[top].append(f.path)
    return [
        {"title": f"Changes in {top}", "summary": f"{len(paths)} file(s) changed.", "files": paths}
        for top, paths in buckets.items()
    ]


def validate_groups(groups: list[dict], files: list[FileDiff]) -> list[dict]:
    """Make sure every real file is in exactly one group.

    - drop paths the model invented
    - drop duplicates (keep first occurrence)
    - put any forgotten files into an "Other changes" group
    - drop groups that end up empty
    """
    real = {f.path for f in files}
    seen: set[str] = set()
    cleaned = []
    for g in groups:
        kept = []
        for p in g.get("files", []):
            if p in real and p not in seen:
                kept.append(p)
                seen.add(p)
        if kept:
            cleaned.append({"title": g.get("title", "Changes"), "summary": g.get("summary", ""), "files": kept})
    missing = [f.path for f in files if f.path not in seen]
    if missing:
        cleaned.append({"title": "Other changes", "summary": "Files not grouped by the model.", "files": missing})
    return cleaned


def call_llm(user_prompt: str) -> dict:
    """The only function that talks to OpenAI, so tests can replace it."""
    from openai import OpenAI

    # Ask for gzip only: some environments ship an old brotli package that
    # crashes the HTTP client when the API replies brotli-compressed.
    client = OpenAI(api_key=settings.openai_api_key, timeout=60, max_retries=2,
                    default_headers={"Accept-Encoding": "gzip, deflate"})
    resp = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.2,  # low = more consistent output across runs
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "pr_review", "strict": True, "schema": RESPONSE_SCHEMA},
        },
    )
    return json.loads(resp.choices[0].message.content)


def analyze(title: str, body: str, files: list[FileDiff]) -> dict:
    """Returns {summary, groups, llm_risks, model, latency_ms, used_fallback}."""
    start = time.perf_counter()
    try:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        raw = call_llm(build_user_prompt(title, body, files))
        groups = validate_groups(raw.get("groups", []), files)
        real = {f.path for f in files}
        llm_risks = [
            {**r, "kind": "llm", "source": "llm"}
            for r in raw.get("risks", [])
            if r.get("path", "") in real or r.get("path", "") == ""
        ]
        return {
            "summary": raw.get("summary", ""),
            "groups": groups,
            "llm_risks": llm_risks,
            "model": settings.openai_model,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "used_fallback": False,
        }
    except Exception as exc:  # any failure -> still return something useful
        return {
            "summary": f"AI summary unavailable ({type(exc).__name__}); grouped by directory instead.",
            "groups": fallback_groups(files),
            "llm_risks": [],
            "model": "fallback",
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "used_fallback": True,
        }
