"""Renders the Markdown comment posted on the pull request."""

MARKER = "<!-- difflens-review -->"
ICON = {"high": "🔴", "medium": "🟠", "low": "⚪"}


def render_comment(review: dict, frontend_url: str) -> str:
    stats = review.get("stats", {})
    lines = [
        MARKER,
        "## 🔍 DiffLens review guide",
        "",
        review.get("summary", ""),
        "",
        f"**{stats.get('files', 0)} files** · +{stats.get('additions', 0)} / -{stats.get('deletions', 0)}",
        "",
        "### Suggested reading order",
    ]
    for i, g in enumerate(review.get("groups", []), 1):
        lines.append(f"{i}. **{g['title']}** ({len(g['files'])} file{'s' if len(g['files']) != 1 else ''}): {g['summary']}")

    risks = review.get("risks", [])
    if risks:
        lines += ["", "### Things to check"]
        for r in risks[:10]:
            where = f" `{r['path']}`:" if r.get("path") else ""
            lines.append(f"- {ICON.get(r['severity'], '•')}{where} {r['message']}")
        if len(risks) > 10:
            lines.append(f"- …and {len(risks) - 10} more in the full view")

    if review.get("id"):
        lines += ["", f"[Open the grouped diff view →]({frontend_url}/reviews/{review['id']})"]
    return "\n".join(lines)


def render_skipped(changed: int, limit: int) -> str:
    return (
        f"{MARKER}\n## 🔍 DiffLens\n\nThis PR changes {changed} lines, more than the {limit}-line limit. "
        "Large PRs are hard for people *and* models to review well; consider splitting it."
    )
