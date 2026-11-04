# Evals: does DiffLens group a PR the way its author would?

**Results:** [results/RESULTS.md](results/RESULTS.md)

## The idea

Grouping quality needs an answer key, and hand-labelling is slow and biased toward
whoever labels. So this eval uses the **PR author's own commits**: when a developer
splits a pull request into several commits, each commit is their statement of
"these files belong together". A file's true group is the commit that changed it most.

## The dataset

`data/prs.json` holds 56 merged pull requests from four well-maintained Python
projects (Flask, Click, Werkzeug, Jinja; all BSD-3-Clause). `build_dataset.py`
reads them straight from local git clones (merge commits record each PR's commits),
so no API access is needed. A PR is kept only if it is a clean test case:

- 2+ authored commits, 3–40 files, at most 2,000 changed lines, 2+ distinct groups
- at most 25% of files changed by more than one commit
- not a branch sync, release, bot update or dependency bump
- commits that look like review fix-ups ("address review", "typo", "lint") never
  own a file another commit also changed

**Held-out set.** `data/holdout.json` holds 153 more PRs from four different
projects (pytest, pip, setuptools, requests). The development set was inspected while improving the prompt;
the held-out set never was, so **held-out scores are the honest result**.

## Prompt versions

Prompts are versioned in `backend/app/analyzer.py`. v1's errors on the development
set had a clear pattern: it over-split PRs (3.5 groups on average vs 2.6 for the
authors) and separated tests from the code they test (authors kept 79 of 113 test
files with their code; v1 kept 48). v2 states the principle that fixes both: a group
is a change you could review or revert on its own, so its tests, docs and changelog
travel with it.

## The metrics

A grouping is compared as **pairs of files**: a pair is "together" if both files are
in the same group, which makes group names irrelevant.

- **Pairwise precision / recall / F1**, micro-averaged over all file pairs.
- **Adjusted Rand Index (ARI)**, averaged per PR. Chance-corrected: 1 = the author's
  exact grouping, ~0 = no better than random. **This is the headline number**: trivial
  strategies can score a high pairwise F1 (putting everything in one group scores 0.73
  here because many PRs have one dominant commit) but score 0 ARI.
- **Exact match**: share of PRs where the grouping is identical to the author's.

DiffLens is scored against five baselines, from trivial to the best simple heuristics,
including its own fallback (top-level folder).

## Run it

```bash
python evals/run_eval.py                          # baselines + cached model runs, free
OPENAI_API_KEY=sk-... python evals/run_eval.py    # + model calls for anything not cached (~$0.10 per prompt per set)
pytest evals                                      # metric unit tests
```

The model sees only the PR title and diff, never commit messages (that would leak
the answer). Responses are cached in `results/cache_<model>_<prompt>.json`, so results are
reproducible and re-runs are free.

## Limitations

- Commits are a proxy for intent, not a perfect label: some authors commit by
  time, not by topic. Filtering removes the noisiest cases but not all.
- All eight projects are Python; results may not transfer to other languages.
- Every comparison is reported with a paired bootstrap 95% confidence interval;
  small differences need more PRs than these sets hold.
