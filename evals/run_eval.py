"""Score DiffLens's grouping against the PR authors' own commits.

    cd DiffLens
    python evals/run_eval.py                 # baselines only (free)
    OPENAI_API_KEY=sk-... python evals/run_eval.py   # + DiffLens with the LLM

Model responses are cached in evals/results/cache_<model>.json, so re-running
costs nothing and results are reproducible. Writes evals/results/RESULTS.md.
"""
import argparse
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))

from app.analyzer import analyze, fallback_groups  # noqa: E402
from app.config import settings  # noqa: E402
from app.diff_parser import parse_files  # noqa: E402

from metrics import ari, groups_to_labels, pair_counts, prf, same_partition  # noqa: E402


# ---------------------------------------------------------------- methods
def single_group(pr, files):
    return {f.path: 0 for f in files}


def one_per_file(pr, files):
    return {f.path: i for i, f in enumerate(files)}


def top_folder(pr, files):
    """What DiffLens falls back to when the model fails."""
    return groups_to_labels(fallback_groups(files))


def parent_folder(pr, files):
    """A stronger heuristic: group by each file's full parent directory."""
    dirs = {}
    return {f.path: dirs.setdefault(f.path.rsplit("/", 1)[0] if "/" in f.path else "", len(dirs)) for f in files}


def code_with_tests(pr, files):
    """Strongest heuristic: pair each test file with the source file it names, else group by folder."""
    labels = parent_folder(pr, files)
    stems = {f.path.rsplit("/", 1)[-1].removesuffix(".py"): f.path for f in files if "test" not in f.path}
    for f in files:
        name = f.path.rsplit("/", 1)[-1].removesuffix(".py")
        if name.startswith("test_") and name[5:] in stems:
            labels[f.path] = labels[stems[name[5:]]]
    return labels


BASELINES = {
    "All files in one group": single_group,
    "One group per file": one_per_file,
    "Top-level folder (DiffLens fallback)": top_folder,
    "Parent folder": parent_folder,
    "Parent folder + test pairing": code_with_tests,
}


def run_difflens(dataset, cache_path: Path, workers: int):
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    def one(pr):
        if pr["id"] in cache:
            return
        files = parse_files(pr["files"])
        # Title only: the description isn't in git, and commit messages would leak the answer.
        result = analyze(pr["title"], "", files)
        cache[pr["id"]] = {"groups": result["groups"], "fallback": result["used_fallback"],
                           "latency_ms": result["latency_ms"]}

    todo = [pr for pr in dataset if pr["id"] not in cache]
    if todo:
        print(f"Calling {settings.openai_model} on {len(todo)} PRs ({len(dataset) - len(todo)} cached)...")
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(one, todo))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=1) + "\n", encoding="utf-8")
    failed = [k for k, v in cache.items() if v["fallback"]]
    if failed:
        print(f"Warning: {len(failed)} PR(s) fell back (API errors): {failed[:5]}")
    return lambda pr, files: groups_to_labels(cache[pr["id"]]["groups"])


# ---------------------------------------------------------------- scoring
def score(dataset, method):
    tp = fp = fn = 0
    aris, exact, per_pr = [], 0, {}
    for pr in dataset:
        files = parse_files(pr["files"])
        truth = pr["labels"]
        pred = method(pr, files)
        a, b, c = pair_counts(truth, pred)
        tp, fp, fn = tp + a, fp + b, fn + c
        r = ari(truth, pred)
        aris.append(r)
        exact += same_partition(truth, pred)
        per_pr[pr["id"]] = round(r, 3)
    p, rc, f1 = prf(tp, fp, fn)
    return {"precision": p, "recall": rc, "f1": f1, "ari": sum(aris) / len(aris),
            "exact": exact / len(dataset), "per_pr": per_pr}


def write_report(dataset, results, path: Path):
    repos = defaultdict(int)
    for pr in dataset:
        repos[pr["repo"]] += 1
    lines = [
        "# Grouping eval results",
        "",
        f"{len(dataset)} merged pull requests from "
        + ", ".join(f"{r} ({n})" for r, n in repos.items())
        + ". Ground truth: each file's group is the author's commit that changed it most. "
        "Pairwise scores are micro-averaged over all file pairs; ARI is averaged per PR.",
        "",
        "| Method | Pairwise precision | Pairwise recall | Pairwise F1 | Mean ARI | Exact match |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, m in results.items():
        lines.append(f"| {name} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | "
                     f"{m['ari']:.2f} | {m['exact']:.0%} |")
    lines += ["", "Regenerate: `python evals/run_eval.py` (see evals/README.md)."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "prs.json")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()
    dataset = json.loads(args.data.read_text(encoding="utf-8"))

    methods = dict(BASELINES)
    if settings.openai_api_key:
        cache = ROOT / "results" / f"cache_{settings.openai_model}.json"
        methods[f"DiffLens ({settings.openai_model})"] = run_difflens(dataset, cache, args.workers)
    else:
        print("OPENAI_API_KEY not set: scoring baselines only.")

    results = {name: score(dataset, fn) for name, fn in methods.items()}
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    write_report(dataset, results, out / "RESULTS.md")

    width = max(len(n) for n in results)
    print(f"\n{'Method':<{width}}  Prec  Rec   F1    ARI   Exact")
    for name, m in results.items():
        print(f"{name:<{width}}  {m['precision']:.2f}  {m['recall']:.2f}  {m['f1']:.2f}  {m['ari']:.2f}  {m['exact']:.0%}")
    print(f"\nWrote {out / 'RESULTS.md'}")


if __name__ == "__main__":
    main()
