"""How close is a predicted grouping of files to the true one?

A grouping is a dict {file path: group id}. Group ids are arbitrary labels, so
we never compare ids directly. Instead we look at PAIRS of files: a pair is
"together" if both files are in the same group.

- pairwise precision: of the pairs we put together, how many truly belong together
- pairwise recall:    of the pairs that truly belong together, how many we put together
- ARI (adjusted Rand index): agreement on all pairs, corrected for chance;
  1 = identical grouping, ~0 = no better than random, can go negative
"""
from itertools import combinations
from math import comb


def pair_counts(truth: dict[str, int], pred: dict[str, int]) -> tuple[int, int, int]:
    """Returns (true positives, false positives, false negatives) over file pairs."""
    tp = fp = fn = 0
    for a, b in combinations(sorted(truth), 2):
        same_true = truth[a] == truth[b]
        same_pred = pred[a] == pred[b]
        if same_true and same_pred:
            tp += 1
        elif same_pred:
            fp += 1
        elif same_true:
            fn += 1
    return tp, fp, fn


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0   # predicted no pairs: nothing wrong claimed
    recall = tp / (tp + fn) if tp + fn else 1.0      # no true pairs: nothing to find
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def ari(truth: dict[str, int], pred: dict[str, int]) -> float:
    files = sorted(truth)
    n = len(files)
    table: dict[tuple[int, int], int] = {}
    rows: dict[int, int] = {}
    cols: dict[int, int] = {}
    for f in files:
        t, p = truth[f], pred[f]
        table[(t, p)] = table.get((t, p), 0) + 1
        rows[t] = rows.get(t, 0) + 1
        cols[p] = cols.get(p, 0) + 1
    index = sum(comb(v, 2) for v in table.values())
    sum_rows = sum(comb(v, 2) for v in rows.values())
    sum_cols = sum(comb(v, 2) for v in cols.values())
    expected = sum_rows * sum_cols / comb(n, 2) if n > 1 else 0.0
    maximum = (sum_rows + sum_cols) / 2
    if maximum == expected:  # degenerate (e.g. both all-singletons): identical or not
        return 1.0 if same_partition(truth, pred) else 0.0
    return (index - expected) / (maximum - expected)


def same_partition(truth: dict[str, int], pred: dict[str, int]) -> bool:
    def blocks(g):
        out: dict[int, set[str]] = {}
        for f, k in g.items():
            out.setdefault(k, set()).add(f)
        return {frozenset(v) for v in out.values()}
    return blocks(truth) == blocks(pred)


def groups_to_labels(groups: list[dict]) -> dict[str, int]:
    """DiffLens groups [{"files": [...]}, ...] -> {path: group index}."""
    return {path: i for i, g in enumerate(groups) for path in g["files"]}
