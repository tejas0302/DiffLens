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

48 PRs: pytest (45), requests (3). Never inspected while developing prompts.

| Method | Pairwise precision | Pairwise recall | Pairwise F1 | Mean ARI | Exact match |
| --- | --- | --- | --- | --- | --- |
| All files in one group | 0.49 | 1.00 | 0.65 | 0.00 | 0% |
| One group per file | 1.00 | 0.00 | 0.00 | 0.08 | 8% |
| Top-level folder (DiffLens fallback) | 0.69 | 0.63 | 0.66 | 0.17 | 17% |
| Parent folder | 0.64 | 0.27 | 0.38 | 0.14 | 15% |
| Parent folder + test pairing | 0.64 | 0.27 | 0.38 | 0.14 | 15% |
| DiffLens v1 (gpt-4.1-mini) | 0.80 | 0.62 | 0.70 | 0.20 | 12% |
| DiffLens v2 (gpt-4.1-mini) | 0.70 | 0.79 | 0.74 | 0.25 | 15% |

- DiffLens v1 (gpt-4.1-mini) vs best baseline (Top-level folder (DiffLens fallback)): ARI +0.03, 95% CI [-0.12, +0.17]
- DiffLens v2 (gpt-4.1-mini) vs best baseline (Top-level folder (DiffLens fallback)): ARI +0.08, 95% CI [-0.07, +0.24]
- DiffLens v2 (gpt-4.1-mini) vs DiffLens v1 (gpt-4.1-mini): ARI +0.06, 95% CI [-0.06, +0.17]

Regenerate: `python evals/run_eval.py`.
