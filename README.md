# DiffLens

**Read pull requests by intent, not by file.**

AI coding tools make PRs bigger and faster than people can review them. GitHub shows a PR as an
alphabetical list of files, which is the wrong order to understand it in. DiffLens is a GitHub App
that, on every pull request:

1. **Groups the diff into logical changes** ("Add rate limiting", "Update tests") and orders them
   the way a reviewer should read them.
2. **Flags what needs a careful look** — security-sensitive files, migrations, dependency bumps,
   possible hard-coded secrets, missing tests — using deterministic rules *plus* LLM judgment.
3. **Posts a review guide as a PR comment** and links to a web view with the grouped diff and a
   "files reviewed" tracker.

**Live:** [diff-lens-five.vercel.app](https://diff-lens-five.vercel.app) · **Example review:** [diff-lens-five.vercel.app/reviews/example](https://diff-lens-five.vercel.app/reviews/example)

<!-- Add a screenshot or GIF here: docs/demo.gif -->

## How it works

```
GitHub PR opened/updated
        │  webhook (HMAC-signed)
        ▼
FastAPI /webhook ── verify signature ── dedupe by commit SHA ── reply 200 in <1s
        │  background task
        ▼
fetch PR files (GitHub App installation token)
        ▼
parse diffs ─► size guard ─► rule-based risks ─► LLM grouping (JSON schema) ─► validate / fallback
        ▼
save to Postgres ─► upsert one PR comment
        ▼
Next.js frontend reads /api/reviews/:id and renders the grouped diff
```

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy 2, httpx, PyJWT |
| AI | OpenAI API with strict JSON-schema structured output |
| Database | Postgres in production, SQLite locally |
| Frontend | Next.js 15 (App Router), React 19, TypeScript |
| Tests | pytest — GitHub and OpenAI are mocked, 15 tests |

### Design decisions
- **Reply to the webhook immediately, analyze in the background.** GitHub gives a webhook
  10 seconds; an LLM call can take longer.
- **Idempotent by `(repo, PR, commit SHA)`.** GitHub can redeliver events; we never review the
  same commit twice or post duplicate comments.
- **Rules + LLM, not LLM alone.** Rules are free, instant, testable and never hallucinate; the LLM
  adds understanding of intent. The LLM's output is validated (every file in exactly one group,
  invented paths dropped) and the app falls back to directory grouping if the model fails.
- **One comment per PR, edited in place**, so new pushes don't spam the thread.
- **Guardrails:** PRs above 2,000 changed lines are skipped with an explanation; each file's patch
  is truncated before it reaches the model to bound cost and latency.

## Run it locally (no GitHub needed)

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add OPENAI_API_KEY to get AI grouping; works without it
python seed_demo.py           # creates a demo review
uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev                   # open http://localhost:3000
```

Run tests: `cd backend && pytest -q`

## Connect it to GitHub

1. **Expose your local backend** (for testing): `npx smee-client` or `ngrok http 8000`, and note the public URL.
2. **Create the GitHub App:** GitHub → Settings → Developer settings → GitHub Apps → New.
   - Webhook URL: `https://<your-backend>/webhook`
   - Webhook secret: a long random string (same value as `GITHUB_WEBHOOK_SECRET`)
   - Repository permissions: **Pull requests: Read**, **Contents: Read**, **Issues: Read & write** (PR comments use the Issues API)
   - Subscribe to events: **Pull request**
3. Generate a **private key** (downloads a `.pem`) and copy the **App ID** into `.env`.
4. **Install the app** on a test repo and open a pull request.

## Deploy

The frontend works on its own: with no backend configured it serves the landing page and a
built-in example review (`/reviews/example`), so the public link never breaks.

1. **Frontend (Vercel):** import the repo, set **Root Directory** to `frontend`, deploy.
2. **Example with real AI output:** `cd backend && OPENAI_API_KEY=sk-... python export_example.py`,
   then commit `frontend/lib/example-review.json`; Vercel redeploys automatically.
3. **Database (Neon):** create a free Postgres project and copy its connection string.
4. **Backend (Render):** New → Blueprint → this repo. `render.yaml` sets it up; paste the values it asks for.
5. **Connect them:** in Vercel set `NEXT_PUBLIC_API_URL` to the Render URL (and optionally
   `NEXT_PUBLIC_INSTALL_URL` to your app's install page), redeploy; point the GitHub App's webhook at
   `https://<render-url>/webhook`.

Render's free tier sleeps after 15 idle minutes, so the first webhook after a quiet spell can take
about a minute; GitHub's "Redeliver" button on the App's Advanced tab retries it.

## Evaluation

Grouping is scored on real merged PRs from eight open-source Python projects, using each PR
author's own commits as the answer key, against five baselines, with a held-out set of 153
PRs that was never inspected while developing prompts. Method, metrics and
limitations: [evals/README.md](evals/README.md) · results: [evals/results/RESULTS.md](evals/results/RESULTS.md).

## Roadmap
- Extend the eval to risk flags: precision/recall against PRs whose follow-up commits fixed a bug
- Stream large PRs file-by-file and cache per commit to cut latency
- Inline review comments on specific lines
- A/B test two summary formats and measure which ones reviewers open
