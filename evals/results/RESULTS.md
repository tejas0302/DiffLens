# Grouping eval results

56 merged pull requests from flask (15), click (15), werkzeug (15), jinja (11). Ground truth: each file's group is the author's commit that changed it most. Pairwise scores are micro-averaged over all file pairs; ARI is averaged per PR.

| Method | Pairwise precision | Pairwise recall | Pairwise F1 | Mean ARI | Exact match |
| --- | --- | --- | --- | --- | --- |
| All files in one group | 0.57 | 1.00 | 0.73 | 0.00 | 0% |
| One group per file | 1.00 | 0.00 | 0.00 | 0.02 | 2% |
| Top-level folder (DiffLens fallback) | 0.79 | 0.60 | 0.68 | 0.23 | 7% |
| Parent folder | 0.84 | 0.37 | 0.51 | 0.21 | 9% |
| Parent folder + test pairing | 0.84 | 0.37 | 0.51 | 0.20 | 9% |

Regenerate: `python evals/run_eval.py` (see evals/README.md).
