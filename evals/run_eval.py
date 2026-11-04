"""Score DiffLens's grouping against the PR authors' own commits.

    cd DiffLens
    python evals/run_eval.py                          # baselines + any cached model runs (free)
    OPENAI_API_KEY=sk-... python evals/run_eval.py    # + calls the model for anything not cached

Two datasets: the development set (data/prs.json), which was inspected while
improving the prompt, and a held-out set (data/holdout.json) from different
projects, which was never looked at. Report held-out numbers as the result.

Model responses are cached per model and prompt version in
results/cache_<model>_<prompt>.json, so re-runs are free and reproducible.
Writes results/RESULTS.md.
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))

from app.analyzer import SYSTEM_PROMPTS, analyze, fallback_groups  # noqa: E402
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


DATASETS = {"Development set": "prs.json", "Held-out set": "holdout.json"}


def load_cache(model: str, version: str) -> tuple[Path, dict]:
    path = ROOT / "results" / f"cache_{model}_{version}.json"
    return path, (json.loads(path.read_text(encoding="utf-8")) if path.exists() else {})


def difflens_method(dataset, model: str, version: str, workers: int):
    """Returns a scoring function, calling the model only for PRs not cached. None if unavailable."""
    path, cache = load_cache(model, version)
    todo = [pr for pr in dataset if pr["id"] not in cache]
    if todo and not settings.openai_api_key:
        print(f"  skip DiffLens {version}: {len(todo)} PRs not cached and OPENAI_API_KEY not set")
        return None

    def one(pr):
        files = parse_files(pr["files"])
        # Title only: the description isn't in git, and commit messages would leak the answer.
        result = analyze(pr["title"], "", files, prompt_version=version)
        cache[pr["id"]] = {"groups": result["groups"], "fallback": result["used_fallback"],
                           "latency_ms": result["latency_ms"]}

    if todo:
        print(f"  calling {model} (prompt {version}) on {len(todo)} PRs...")
        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(one, todo))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    failed = [pr["id"] for pr in dataset if cache[pr["id"]]["fallback"]]
    if failed:
        print(f"  warning: {len(failed)} PR(s) fell back after API errors: {failed[:5]}")
    return lambda pr, files: groups_to_labels(cache[pr["id"]]["groups"])


# ---------------------------------------------------------------- scoring
def score(dataset, method):
    tp = fp = fn = 0
    exact, per_pr = 0, {}
    for pr in dataset:
        files = parse_files(pr["files"])
        truth = pr["labels"]
        pred = method(pr, files)
        a, b, c = pair_counts(truth, pred)
        tp, fp, fn = tp + a, fp + b, fn + c
        per_pr[pr["id"]] = ari(truth, pred)
        exact += same_partition(truth, pred)
    p, rc, f1 = prf(tp, fp, fn)
    return {"precision": p, "recall": rc, "f1": f1, "ari": sum(per_pr.values()) / len(per_pr),
            "exact": exact / len(dataset), "per_pr": per_pr}


def paired_ci(a: dict, b: dict, n_boot: int = 10000, seed: int = 0) -> tuple[float, float, float]:
    """Mean per-PR ARI difference (a - b) with a 95% bootstrap confidence interval."""
    diffs = [a[k] - b[k] for k in a]
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(n_boot))
    return sum(diffs) / len(diffs), means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def comparisons(results: dict) -> list[str]:
    baselines = {k: v for k, v in results.items() if not k.startswith("DiffLens")}
    best = max(baselines, key=lambda k: baselines[k]["ari"])
    models = [k for k in results if k.startswith("DiffLens")]
    out = []
    for m in models:
        d, lo, hi = paired_ci(results[m]["per_pr"], results[best]["per_pr"])
        out.append(f"- {m} vs best baseline ({best}): ARI {d:+.2f}, 95% CI [{lo:+.2f}, {hi:+.2f}]")
    if len(models) >= 2:
        d, lo, hi = paired_ci(results[models[-1]]["per_pr"], results[models[0]]["per_pr"])
        out.append(f"- {models[-1]} vs {models[0]}: ARI {d:+.2f}, 95% CI [{lo:+.2f}, {hi:+.2f}]")
    return out


def table(results: dict) -> list[str]:
    lines = ["| Method | Pairwise precision | Pairwise recall | Pairwise F1 | Mean ARI | Exact match |",
             "| --- | --- | --- | --- | --- | --- |"]
    for name, m in results.items():
        lines.append(f"| {name} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | "
                     f"{m['ari']:.2f} | {m['exact']:.0%} |")
    return lines


def write_report(sections: dict, path: Path):
    lines = ["# Grouping eval results", "",
             "Ground truth: each file's group is the PR author's commit that changed it most. "
             "Pairwise scores are micro-averaged over file pairs; ARI (1 = the author's grouping, "
             "0 = chance) is averaged per PR. Intervals are paired bootstrap 95% CIs over PRs. "
             "Method and limitations: [../README.md](../README.md).", ""]
    for title, (dataset, results) in sections.items():
        repos = defaultdict(int)
        for pr in dataset:
            repos[pr["repo"]] += 1
        note = (" Never inspected while developing prompts." if "Held-out" in title
                else " Inspected while developing prompt v2, so v2 scores here are optimistic.")
        lines += [f"## {title}", "",
                  f"{len(dataset)} PRs: " + ", ".join(f"{r} ({n})" for r, n in repos.items()) + "." + note,
                  "", *table(results), "", *comparisons(results), ""]
    lines += ["Regenerate: `python evals/run_eval.py`."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", nargs="+", default=list(SYSTEM_PROMPTS))
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()
    model = settings.openai_model

    sections, saved = {}, {}
    for title, filename in DATASETS.items():
        path = ROOT / "data" / filename
        if not path.exists():
            continue
        dataset = json.loads(path.read_text(encoding="utf-8"))
        print(f"{title}: {len(dataset)} PRs")
        methods = dict(BASELINES)
        for version in args.prompts:
            fn = difflens_method(dataset, model, version, args.workers)
            if fn:
                methods[f"DiffLens {version} ({model})"] = fn
        results = {name: score(dataset, fn) for name, fn in methods.items()}
        sections[title] = (dataset, results)
        saved[title] = {k: {**v, "per_pr": {i: round(x, 4) for i, x in v["per_pr"].items()}}
                        for k, v in results.items()}

        width = max(len(n) for n in results)
        print(f"\n  {'Method':<{width}}  Prec  Rec   F1    ARI   Exact")
        for name, m in results.items():
            print(f"  {name:<{width}}  {m['precision']:.2f}  {m['recall']:.2f}  {m['f1']:.2f}  "
                  f"{m['ari']:.2f}  {m['exact']:.0%}")
        for line in comparisons(results):
            print("  " + line[2:])
        print()

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(saved, indent=1) + "\n", encoding="utf-8")
    write_report(sections, out / "RESULTS.md")
    print(f"Wrote {out / 'RESULTS.md'}")


if __name__ == "__main__":
    main()
