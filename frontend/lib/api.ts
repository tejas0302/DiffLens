import type { ReviewDetail, ReviewSummary } from "./types";

// NEXT_PUBLIC_ variables are baked into the build and visible to the browser.
// That's fine here: it's just the backend's public URL, not a secret.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T | null> {
  // no-store: reviews change (pending -> done), so never serve a cached copy.
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`);
  return (await res.json()) as T;
}

export const listReviews = () => getJSON<ReviewSummary[]>("/api/reviews");
export const getReview = (id: string) => getJSON<ReviewDetail>(`/api/reviews/${encodeURIComponent(id)}`);
