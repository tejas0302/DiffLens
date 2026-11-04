import Link from "next/link";
import { listReviews } from "@/lib/api";
import type { ReviewSummary } from "@/lib/types";

// A Server Component: this runs on the server, so the browser gets finished
// HTML and never needs to know the API exists for this page.
export const dynamic = "force-dynamic";

export default async function Home() {
  let reviews: ReviewSummary[] = [];
  let error = "";
  try {
    reviews = (await listReviews()) ?? [];
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <>
      <h1>Recent reviews</h1>
      {error && <p className="notice error">Could not reach the backend: {error}</p>}
      {!error && reviews.length === 0 && (
        <div className="empty">
          <p>No reviews yet.</p>
          <p className="muted">Install the GitHub App on a repo and open a pull request.</p>
        </div>
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
    </>
  );
}
