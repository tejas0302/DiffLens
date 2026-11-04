# Grouping eval results

Ground truth: each file's group is the PR author's commit that changed it most. Pairwise scores are micro-averaged over file pairs; ARI (1 = the author's grouping, 0 = chance) is averaged per PR. Intervals are paired bootstrap 95% CIs over PRs. Method and limitations: [../README.md](../README.md).

## Development set

56 PRs: flask (15), click (15), werkzeug (15), jinja (11). Inspected while developing prompt v2, so v2 scores here are optimistic.

| Method | Pairwise precision | Pairwise recall | Pairwise F1 | Mean ARI | Exact match |
| --- | --- | --- | --- | --- | --- |
| All files in one group | 0.57 | 1.00 | 0.73 | 0.00 | 0% |
| One group per file | 1.00 | 0.00 | 0.00 | 0.02 | 2% |
| Top-level folder (DiffLens fallback) | 0.79 | 0.60 | 0.68 | 0.23 | 7% |
| Parent folder | 0.84 | 0.37 | 0.51 | 0.21 | 9% |
| Parent folder + test pairing | 0.84 | 0.37 | 0.51 | 0.20 | 9% |
| DiffLens v1 (gpt-4.1-mini) | 0.86 | 0.60 | 0.71 | 0.33 | 12% |
| DiffLens v2 (gpt-4.1-mini) | 0.81 | 0.71 | 0.76 | 0.42 | 25% |

- DiffLens v1 (gpt-4.1-mini) vs best baseline (Top-level folder (DiffLens fallback)): ARI +0.11, 95% CI [+0.02, +0.20]
- DiffLens v2 (gpt-4.1-mini) vs best baseline (Top-level folder (DiffLens fallback)): ARI +0.19, 95% CI [+0.07, +0.33]
- DiffLens v2 (gpt-4.1-mini) vs DiffLens v1 (gpt-4.1-mini): ARI +0.09, 95% CI [-0.03, +0.20]

## Held-out set

153 PRs: pytest (50), requests (3), pip (50), setuptools (50). Never inspected while developing prompts.

| Method | Pairwise precision | Pairwise recall | Pairwise F1 | Mean ARI | Exact match |
| --- | --- | --- | --- | --- | --- |
| All files in one group | 0.45 | 1.00 | 0.62 | 0.00 | 0% |
| One group per file | 1.00 | 0.00 | 0.00 | 0.08 | 8% |
| Top-level folder (DiffLens fallback) | 0.59 | 0.70 | 0.64 | 0.21 | 16% |
| Parent folder | 0.68 | 0.28 | 0.40 | 0.18 | 10% |
| Parent folder + test pairing | 0.66 | 0.29 | 0.41 | 0.20 | 12% |
| DiffLens v1 (gpt-4.1-mini) | 0.71 | 0.55 | 0.62 | 0.24 | 12% |
| DiffLens v2 (gpt-4.1-mini) | 0.69 | 0.75 | 0.72 | 0.25 | 10% |

- DiffLens v1 (gpt-4.1-mini) vs best baseline (Top-level folder (DiffLens fallback)): ARI +0.04, 95% CI [-0.04, +0.12]
- DiffLens v2 (gpt-4.1-mini) vs best baseline (Top-level folder (DiffLens fallback)): ARI +0.04, 95% CI [-0.04, +0.12]
- DiffLens v2 (gpt-4.1-mini) vs DiffLens v1 (gpt-4.1-mini): ARI +0.01, 95% CI [-0.06, +0.07]

Regenerate: `python evals/run_eval.py`.
