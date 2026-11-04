// These mirror the JSON the FastAPI backend returns (see backend/app/main.py).
// Keeping them in one file means a backend change shows up as a type error here.

export type Severity = "high" | "medium" | "low";

export interface Risk {
  severity: Severity;
  kind: string;
  path: string;
  message: string;
  source: "rule" | "llm";
}

export interface Group {
  title: string;
  summary: string;
  files: string[];
}

export interface Hunk {
  header: string;
  old_start: number;
  new_start: number;
  lines: string[];
}

export interface FileDiff {
  path: string;
  status: string;
  additions: number;
  deletions: number;
  patch: string;
  hunks: Hunk[];
}

export interface Stats {
  files: number;
  additions: number;
  deletions: number;
}

export interface ReviewSummary {
  id: number;
  repo: string;
  pr_number: number;
  title: string;
  author: string;
  status: "pending" | "done" | "skipped" | "failed";
  stats: Stats;
  risk_count: number;
  high_risk_count: number;
  created_at: string | null;
}

export interface ReviewDetail extends ReviewSummary {
  head_sha: string;
  pr_url: string;
  summary: string;
  groups: Group[];
  risks: Risk[];
  files: FileDiff[];
  model: string;
  latency_ms: number;
  error: string;
}
