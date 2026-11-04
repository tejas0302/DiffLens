import Link from "next/link";
import { EXAMPLE_ID, INSTALL_URL, REPO_URL, listReviews } from "@/lib/api";
import type { ReviewSummary } from "@/lib/types";

// A Server Component: this runs on the server, so the browser gets finished
// HTML and never needs to know the API exists for this page.
export const dynamic = "force-dynamic";

const STEPS = [
  {
    title: "Grouped by intent",
    body: "Files are grouped into the few logical changes the author made, ordered the way a reviewer should read them.",
  },
  {
    title: "Risks flagged twice over",
    body: "Deterministic rules catch secrets, migrations, auth code and missing tests; an LLM adds judgment on top. Each flag says which one raised it.",
  },
  {
    title: "Right where you review",
    body: "A GitHub App posts one review-guide comment per PR and keeps it updated on every push, with a link to the full grouped diff.",
  },
];

export default async function Home() {
  let reviews: ReviewSummary[] | null = null;
  let error = "";
  try {
    reviews = await listReviews();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <>
      <section className="hero">
        <p className="eyebrow">GitHub App · open source</p>
        <h1 className="hero-title">Review AI-sized pull requests in the order they make sense.</h1>
        <p className="hero-lead">
          GitHub lists a pull request as an alphabetical wall of files. DiffLens turns it into a short
          review guide: what changed, in what order to read it, and what to check carefully.
        </p>
        <div className="cta-row">
          <Link href={`/reviews/${EXAMPLE_ID}`} className="btn primary">See an example review →</Link>
          {INSTALL_URL && (
            <a href={INSTALL_URL} className="btn" target="_blank" rel="noreferrer">Install on GitHub</a>
          )}
          <a href={REPO_URL} className="btn" target="_blank" rel="noreferrer">View source</a>
        </div>
      </section>

      <section className="features">
        {STEPS.map((s) => (
          <div key={s.title} className="feature">
            <h3>{s.title}</h3>
            <p>{s.body}</p>
          </div>
        ))}
      </section>

      <section className="stack muted small">
        FastAPI · Postgres · OpenAI structured outputs · Next.js · TypeScript
      </section>

      {reviews !== null && (
        <section>
          <h2>Recent reviews</h2>
          {error && <p className="notice">The review service is waking up. Refresh in a minute.</p>}
          {!error && reviews.length === 0 && (
            <p className="muted">No reviews yet. Install the app on a repo and open a pull request.</p>
          )}
          <ul className="review-list">
            {reviews.map((r) => (
              <li key={r.id}>
                <Link href={`/reviews/${r.id}`} className="review-row">
                  <div>
                    <div className="row-title">{r.title || `PR #${r.pr_number}`}</div>
                    <div className="muted small">
                      {r.repo} #{r.pr_number} · {r.author}
                    </div>
                  </div>
                  <div className="row-meta">
                    <span className="diffstat">
                      <span className="add">+{r.stats?.additions ?? 0}</span>{" "}
                      <span className="del">-{r.stats?.deletions ?? 0}</span>
                    </span>
                    {r.high_risk_count > 0 && <span className="pill high">{r.high_risk_count} high</span>}
                    <span className={`pill status-${r.status}`}>{r.status}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      {reviews === null && error && <p className="notice">{error}</p>}
    </>
  );
}
