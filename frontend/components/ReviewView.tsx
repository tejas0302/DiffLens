"use client";
// "use client" = this component runs in the browser, because it has
// interactive state (collapsing groups, ticking files off as reviewed).

import { useMemo, useState } from "react";
import type { FileDiff, ReviewDetail, Risk } from "@/lib/types";
import DiffFile from "./DiffFile";

const SEVERITY_ICON: Record<string, string> = { high: "●", medium: "●", low: "○" };

export default function ReviewView({ review }: { review: ReviewDetail }) {
  // Look-up tables built once per render instead of searching arrays repeatedly.
  const fileByPath = useMemo(
    () => new Map<string, FileDiff>(review.files.map((f) => [f.path, f])),
    [review.files],
  );
  const risksByPath = useMemo(() => {
    const m = new Map<string, Risk[]>();
    for (const r of review.risks) {
      if (!r.path) continue;
      m.set(r.path, [...(m.get(r.path) ?? []), r]);
    }
    return m;
  }, [review.risks]);

  const [reviewed, setReviewed] = useState<Set<string>>(new Set());
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

  const toggle = <T,>(set: Set<T>, value: T): Set<T> => {
    // React state must be replaced, not mutated, so React notices the change.
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  };

  const total = review.files.length;
  const done = reviewed.size;

  return (
    <article>
      <div className="review-head">
        <div>
          <h1>{review.title || `PR #${review.pr_number}`}</h1>
          <div className="muted">
            {review.repo} #{review.pr_number} · {review.author} · <code>{review.head_sha.slice(0, 7)}</code>
            {review.pr_url && (
              <>
                {" · "}
                <a href={review.pr_url} target="_blank" rel="noreferrer">Open on GitHub ↗</a>
              </>
            )}
          </div>
        </div>
        <div className="progress" aria-label="review progress">
          <div className="progress-label">{done}/{total} files reviewed</div>
          <div className="progress-bar">
            <div style={{ width: total ? `${(done / total) * 100}%` : "0%" }} />
          </div>
        </div>
      </div>

      {review.status === "failed" && <p className="notice error">Review failed: {review.error}</p>}
      {review.status === "pending" && <p className="notice">Analysis in progress. Refresh in a few seconds.</p>}

      {review.summary && <p className="summary">{review.summary}</p>}

      <div className="meta-row muted small">
        <span className="add">+{review.stats.additions}</span>{" "}
        <span className="del">-{review.stats.deletions}</span> across {review.stats.files} files
        {review.model && <> · model: {review.model}</>}
        {review.latency_ms > 0 && <> · {(review.latency_ms / 1000).toFixed(1)}s</>}
      </div>

      {review.risks.length > 0 && (
        <section className="risks">
          <h2>Things to check</h2>
          <ul>
            {review.risks.map((r, i) => (
              <li key={i} className={`risk ${r.severity}`}>
                <span className="dot">{SEVERITY_ICON[r.severity]}</span>
                {r.path ? <a href={`#file-${encodeURIComponent(r.path)}`}><code>{r.path}</code></a> : null}
                <span>{r.message}</span>
                <span className="source">{r.source === "llm" ? "AI" : "rule"}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2>Changes, in suggested reading order</h2>
        {review.groups.map((g, gi) => {
          const isCollapsed = collapsed.has(gi);
          const groupDone = g.files.filter((p) => reviewed.has(p)).length;
          return (
            <div key={gi} className="group">
              <button className="group-head" onClick={() => setCollapsed((c) => toggle(c, gi))}>
                <span className="chev">{isCollapsed ? "▸" : "▾"}</span>
                <span className="group-num">{gi + 1}</span>
                <span className="group-title">{g.title}</span>
                <span className="muted small">{groupDone}/{g.files.length}</span>
              </button>
              {!isCollapsed && (
                <div className="group-body">
                  <p className="group-summary">{g.summary}</p>
                  {g.files.map((path) => {
                    const file = fileByPath.get(path);
                    if (!file) return null;
                    return (
                      <DiffFile
                        key={path}
                        file={file}
                        risks={risksByPath.get(path) ?? []}
                        reviewed={reviewed.has(path)}
                        onToggleReviewed={() => setReviewed((s) => toggle(s, path))}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </section>
    </article>
  );
}
