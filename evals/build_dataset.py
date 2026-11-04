"""Build the grouping eval set from real, merged pull requests.

Ground truth = the PR author's own commits. When a developer splits a PR into
several commits, each commit is their statement of "these files belong
together". A file's label is the commit that changed it most.

Works offline on local clones of repos that merge PRs with merge commits:

    git clone --shallow-since=2021-01-01 https://github.com/pallets/flask
    python evals/build_dataset.py path/to/flask path/to/click ... --out evals/data/prs.json

Only clean cases are kept (see `keep`): 2+ real commits, 3-40 files, at most
2,000 changed lines, at least 2 distinct groups, and few files shared between
commits. Commits that look like review fix-ups are not allowed to own a file
another commit also changed, since "address review comments" is not intent.
"""
import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

FIXUP = re.compile(r"\b(fixup|squash|review|typo|lint|format|formatting|wip|nit|pre-commit|changelog|changes)\b", re.I)
SKIP_FILE = re.compile(r"(\.lock$|lock\.json$|\.png$|\.jpg$|\.svg$|\.ico$)")
MAX_LINES = 2000
NOT_A_PR = re.compile(
    r"^Merge (branch|remote|stable|tag|commit|[\d.]+x)|`?stable`? into|into (main|master)\b|resolve (merge )?conflict"
    r"|pre-commit|\[bot\]|dependabot|^Bump |release|update[- ]requirements|update[- ]tools", re.I)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=True).stdout


def numstat(repo: Path, *rev: str) -> dict[str, tuple[int, int]]:
    out = {}
    for line in git(repo, "diff", "--numstat", "--no-renames", *rev).splitlines():
        a, d, path = line.split("\t", 2)
        out[path] = (int(a) if a != "-" else 0, int(d) if d != "-" else 0)
    return out


def status_map(repo: Path, rev: str) -> dict[str, str]:
    names = {"A": "added", "D": "removed", "M": "modified"}
    out = {}
    for line in git(repo, "diff", "--name-status", "--no-renames", rev).splitlines():
        code, path = line.split("\t", 1)
        out[path] = names.get(code[0], "modified")
    return out


def pr_from_merge(repo: Path, merge: str, subject: str) -> dict | None:
    base, tip = f"{merge}^1", f"{merge}^2"
    commits = git(repo, "rev-list", "--no-merges", "--reverse", f"{base}..{tip}").split()
    if len(commits) < 2:
        return None
    pr_range = f"{base}...{tip}"
    files = {p: s for p, s in numstat(repo, pr_range).items() if not SKIP_FILE.search(p)}
    total = sum(a + d for a, d in files.values())
    if not (3 <= len(files) <= 40) or total > MAX_LINES:
        return None

    # Which commits changed each file, and by how much.
    touched: dict[str, list[tuple[int, int, bool]]] = defaultdict(list)
    for i, sha in enumerate(commits):
        msg = git(repo, "log", "-1", "--format=%s", sha)
        for path, (a, d) in numstat(repo, f"{sha}^", sha).items():
            if path in files:
                touched[path].append((i, a + d, bool(FIXUP.search(msg))))

    labels, shared = {}, 0
    for path in files:
        hits = touched.get(path, [])
        if not hits:
            continue
        if len({i for i, _, _ in hits}) > 1:
            shared += 1
        real = [h for h in hits if not h[2]] or hits      # prefer non-fix-up commits
        labels[path] = max(real, key=lambda h: h[1])[0]   # commit with the most changed lines
    if len(labels) < len(files) or shared / len(files) > 0.25 or len(set(labels.values())) < 2:
        return None

    statuses = status_map(repo, pr_range)
    gh_files = []
    for path, (a, d) in files.items():
        patch = git(repo, "diff", "--no-renames", pr_range, "--", path)
        patch = patch[patch.find("@@"):] if "@@" in patch else ""
        gh_files.append({"filename": path, "status": statuses.get(path, "modified"),
                         "additions": a, "deletions": d, "patch": patch})

    # Renumber groups 0..k-1 in first-appearance order.
    order = {g: n for n, g in enumerate(dict.fromkeys(labels[f["filename"]] for f in gh_files))}
    m = re.search(r"#(\d+)", subject)
    return {
        "id": f"{repo.name}#{m.group(1) if m else merge[:8]}",
        "repo": repo.name,
        "title": re.sub(r"\s*\(#\d+\)$", "", subject).removeprefix("Merge pull request "),
        "files": gh_files,
        "labels": {p: order[g] for p, g in labels.items()},
        "n_commits": len(commits),
        "shared_files": shared,
    }


def keep_merges(repo: Path) -> list[tuple[str, str]]:
    out = []
    raw = git(repo, "log", "--merges", "--format=%H%x1f%s%x1f%b%x1e")
    for rec in raw.split("\x1e"):
        if not rec.strip():
            continue
        sha, subject, body = (rec.strip("\n").split("\x1f") + ["", ""])[:3]
        # Branch syncs, bot updates and releases are not authored changes.
        # Check the raw subject too: it holds the branch name ("from pallets/release-2.3.2").
        if NOT_A_PR.search(subject):
            continue
        # GitHub writes "Merge pull request #N from owner/branch" with the PR title as the body.
        if subject.startswith("Merge pull request") and body.strip():
            num = re.search(r"#\d+", subject)
            subject = f"{body.strip().splitlines()[0]}" + (f" ({num.group(0)})" if num else "")
            if NOT_A_PR.search(subject):
                continue
        out.append((sha, subject))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data" / "prs.json")
    ap.add_argument("--per-repo", type=int, default=15)
    args = ap.parse_args()

    dataset = []
    for repo in args.repos:
        kept = 0
        for sha, subject in keep_merges(repo):
            try:
                pr = pr_from_merge(repo, sha, subject)
            except subprocess.CalledProcessError:
                continue  # parent missing from a shallow clone
            if pr:
                dataset.append(pr)
                kept += 1
                if kept >= args.per_repo:
                    break
        print(f"{repo.name}: {kept} PRs")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dataset, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {len(dataset)} PRs to {args.out}")


if __name__ == "__main__":
    main()
