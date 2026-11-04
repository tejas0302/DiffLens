"""Turns GitHub's "list pull request files" response into our own clean structure.

GitHub returns, per file: filename, status (added/modified/removed/renamed),
additions, deletions, and `patch` (the unified diff text). Large or binary
files come back with no `patch` at all, so we must handle that.
"""
import re
from dataclasses import asdict, dataclass, field

# Matches a hunk header like "@@ -10,7 +10,9 @@ def foo():"
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


@dataclass
class Hunk:
    header: str
    old_start: int
    new_start: int
    lines: list[str] = field(default_factory=list)  # raw lines incl. +/-/space prefix


@dataclass
class FileDiff:
    path: str
    status: str
    additions: int
    deletions: int
    patch: str            # may be "" for binary / huge files
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def added_lines(self) -> list[str]:
        return [l[1:] for h in self.hunks for l in h.lines if l.startswith("+")]

    @property
    def removed_lines(self) -> list[str]:
        return [l[1:] for h in self.hunks for l in h.lines if l.startswith("-")]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hunks"] = [asdict(h) for h in self.hunks]
        return d


def parse_patch(patch: str) -> list[Hunk]:
    """Split one file's unified diff into hunks."""
    hunks: list[Hunk] = []
    current: Hunk | None = None
    for line in patch.splitlines():
        m = HUNK_HEADER.match(line)
        if m:
            current = Hunk(header=line, old_start=int(m.group(1)), new_start=int(m.group(3)))
            hunks.append(current)
        elif current is not None:
            current.lines.append(line)
    return hunks


def parse_files(github_files: list[dict]) -> list[FileDiff]:
    result = []
    for f in github_files:
        patch = f.get("patch") or ""
        result.append(
            FileDiff(
                path=f["filename"],
                status=f.get("status", "modified"),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                patch=patch,
                hunks=parse_patch(patch),
            )
        )
    return result


def diff_stats(files: list[FileDiff]) -> dict:
    return {
        "files": len(files),
        "additions": sum(f.additions for f in files),
        "deletions": sum(f.deletions for f in files),
    }
