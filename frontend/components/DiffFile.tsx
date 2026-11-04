"use client";

import { useState } from "react";
import type { FileDiff, Risk } from "@/lib/types";

interface Props {
  file: FileDiff;
  risks: Risk[];
  reviewed: boolean;
  onToggleReviewed: () => void;
}

// Very large patches freeze the browser if rendered all at once,
// so we show the first N lines and let the user expand.
const PREVIEW_LINES = 300;

function lineClass(line: string): string {
  if (line.startsWith("@@")) return "line hunk-line";
  if (line.startsWith("+")) return "line add-line";
  if (line.startsWith("-")) return "line del-line";
  if (line.startsWith("\\")) return "line meta-line"; // "\ No newline at end of file"
  return "line";
}

export default function DiffFile({ file, risks, reviewed, onToggleReviewed }: Props) {
  const [showAll, setShowAll] = useState(false);
  // Each hunk header ("@@ -10,3 +10,8 @@") is followed by its lines.
  const allLines = file.hunks.flatMap((h) => [h.header, ...h.lines]);
  const lines = showAll ? allLines : allLines.slice(0, PREVIEW_LINES);
  const worst = risks.find((r) => r.severity === "high") ?? risks[0];

  return (
    <div id={`file-${encodeURIComponent(file.path)}`} className={`file ${reviewed ? "is-reviewed" : ""}`}>
      <div className="file-head">
        <label className="check">
          <input type="checkbox" checked={reviewed} onChange={onToggleReviewed} />
          <code>{file.path}</code>
        </label>
        <span className={`status ${file.status}`}>{file.status}</span>
        <span className="diffstat small">
          <span className="add">+{file.additions}</span> <span className="del">-{file.deletions}</span>
        </span>
        {worst && <span className={`pill ${worst.severity}`}>{risks.length} flag{risks.length > 1 ? "s" : ""}</span>}
      </div>

      {risks.length > 0 && (
        <ul className="file-risks">
          {risks.map((r, i) => (
            <li key={i} className={r.severity}>{r.message}</li>
          ))}
        </ul>
      )}

      {!reviewed && (
        allLines.length === 0 ? (
          <p className="muted small pad">No text diff available (binary or very large file).</p>
        ) : (
          <pre className="diff">
            {lines.map((l, i) => (
              <div key={i} className={lineClass(l)}>{l || " "}</div>
            ))}
            {!showAll && allLines.length > PREVIEW_LINES && (
              <button className="show-more" onClick={() => setShowAll(true)}>
                Show {allLines.length - PREVIEW_LINES} more lines
              </button>
            )}
          </pre>
        )
      )}
    </div>
  );
}
