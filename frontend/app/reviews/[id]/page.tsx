import Link from "next/link";
import { notFound } from "next/navigation";
import { EXAMPLE_ID, getReview } from "@/lib/api";
import ReviewView from "@/components/ReviewView";

export const dynamic = "force-dynamic";

// In Next.js 15, route params arrive as a Promise.
export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let review;
  try {
    review = await getReview(id);
  } catch {
    return (
      <>
        <Link href="/" className="back">← Home</Link>
        <p className="notice">The review service is waking up (free hosting sleeps when idle). Refresh in a minute.</p>
      </>
    );
  }
  if (!review) notFound();
  const isExample = id === EXAMPLE_ID;

  return (
    <>
      <Link href="/" className="back">← Home</Link>
      {isExample && (
        <p className="notice">
          Example review of a sample pull request, produced by the same pipeline that runs on real PRs
          {review.model === "fallback"
            ? " (generated without the AI step, so files are grouped by folder)."
            : ` (model: ${review.model}).`}{" "}
          Tick files off as you read; your progress stays in this tab.
        </p>
      )}
      <ReviewView review={review} />
    </>
  );
}
