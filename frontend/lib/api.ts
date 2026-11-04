import type { ReviewDetail, ReviewSummary } from "./types";
import example from "./example-review.json";

// NEXT_PUBLIC_ variables are baked into the build and visible to the browser.
// That's fine here: it's just the backend's public URL, not a secret.
// Unset = "example mode": the site still works, showing only the built-in example.
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
export const REPO_URL = "https://github.com/tejas0302/DiffLens";
export const INSTALL_URL = process.env.NEXT_PUBLIC_INSTALL_URL ?? "";

export const EXAMPLE_ID = "example";
export const exampleReview = example as ReviewDetail;

async function getJSON<T>(path: string): Promise<T | null> {
  // no-store: reviews change (pending -> done), so never serve a cached copy.
  // The timeout matters on free hosting, where a sleeping backend can take ~50s to wake.
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`);
  return (await res.json()) as T;
}

/** null = no backend configured (example mode). */
export async function listReviews(): Promise<ReviewSummary[] | null> {
  if (!API_URL) return null;
  return (await getJSON<ReviewSummary[]>("/api/reviews")) ?? [];
}

export async function getReview(id: string): Promise<ReviewDetail | null> {
  if (id === EXAMPLE_ID) return exampleReview;
  if (!API_URL || !/^\d+$/.test(id)) return null;
  return getJSON<ReviewDetail>(`/api/reviews/${id}`);
}
