import Link from "next/link";
import { notFound } from "next/navigation";
import { getReview } from "@/lib/api";
import ReviewView from "@/components/ReviewView";

export const dynamic = "force-dynamic";

// In Next.js 15, route params arrive as a Promise.
export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const review = await getReview(id);
  if (!review) notFound();

  return (
    <>
      <Link href="/" className="back">← All reviews</Link>
      <ReviewView review={review} />
    </>
  );
}
