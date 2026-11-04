"""Unit tests for parsing, risk rules, and LLM-output validation."""
from app import analyzer
from app.analyzer import analyze, fallback_groups, validate_groups
from app.diff_parser import diff_stats, parse_files, parse_patch
from app.risk import find_risks

from .conftest import SAMPLE_FILES


def test_parse_patch_splits_hunks():
    patch = "@@ -1,2 +1,3 @@ header\n a\n+b\n@@ -20,1 +21,1 @@\n-c\n+d\n"
    hunks = parse_patch(patch)
    assert len(hunks) == 2
    assert hunks[0].old_start == 1 and hunks[0].new_start == 1
    assert hunks[1].old_start == 20 and hunks[1].new_start == 21
    assert hunks[1].lines == ["-c", "+d"]


def test_parse_files_handles_missing_patch():
    files = parse_files(SAMPLE_FILES)
    png = next(f for f in files if f.path.endswith(".png"))
    assert png.patch == "" and png.hunks == []
    assert diff_stats(files) == {"files": 4, "additions": 11, "deletions": 1}


def test_risk_rules():
    kinds = {(r["kind"], r["path"]) for r in find_risks(parse_files(SAMPLE_FILES))}
    assert ("security", "src/auth/login.py") in kinds
    assert ("dependency", "requirements.txt") in kinds
    assert ("missing_tests", "") in kinds
    assert ("debug_leftover", "src/auth/login.py") in kinds
    assert ("no_patch", "docs/logo.png") in kinds


def test_secret_detection_and_sorting():
    files = parse_files([{
        "filename": "app.py", "status": "modified", "additions": 1, "deletions": 0,
        "patch": '@@ -1 +1,2 @@\n x = 1\n+API_KEY = "sk_live_abcdefghijklmnop"\n',
    }])
    risks = find_risks(files)
    assert risks[0]["kind"] == "secret" and risks[0]["severity"] == "high"


def test_tests_present_means_no_missing_tests_flag():
    files = parse_files(SAMPLE_FILES + [{
        "filename": "tests/test_login.py", "status": "added", "additions": 3, "deletions": 0,
        "patch": "@@ -0,0 +1,3 @@\n+def test_x():\n+    assert True\n+\n",
    }])
    assert not any(r["kind"] == "missing_tests" for r in find_risks(files))


def test_validate_groups_repairs_bad_llm_output():
    files = parse_files(SAMPLE_FILES)
    groups = [
        {"title": "Rate limiting", "summary": "s", "files": ["src/auth/login.py", "src/auth/rate_limit.py"]},
        # duplicate + hallucinated path
        {"title": "Dupes", "summary": "s", "files": ["src/auth/login.py", "src/made_up.py"]},
    ]
    out = validate_groups(groups, files)
    all_paths = [p for g in out for p in g["files"]]
    assert sorted(all_paths) == sorted(f.path for f in files)   # each file exactly once
    assert "src/made_up.py" not in all_paths
    assert out[-1]["title"] == "Other changes"                 # forgotten files rescued
    assert not any(g["title"] == "Dupes" for g in out)         # emptied group dropped


def test_analyze_falls_back_without_api_key():
    result = analyze("t", "b", parse_files(SAMPLE_FILES))
    assert result["used_fallback"] is True
    assert {g["title"] for g in result["groups"]} == {"Changes in src", "Changes in (root)", "Changes in docs"}


def test_analyze_uses_llm_output(monkeypatch):
    # Settings is a frozen dataclass; object.__setattr__ bypasses that for the test.
    object.__setattr__(analyzer.settings, "openai_api_key", "fake")
    fake = {
        "summary": "Adds login rate limiting.",
        "groups": [{"title": "Rate limiting", "summary": "s", "files": [f["filename"] for f in SAMPLE_FILES]}],
        "risks": [
            {"severity": "high", "path": "src/auth/rate_limit.py", "message": "In-memory cache resets on restart."},
            {"severity": "low", "path": "invented.py", "message": "hallucinated"},
        ],
    }
    monkeypatch.setattr(analyzer, "call_llm", lambda prompt: fake)
    try:
        result = analyze("t", "b", parse_files(SAMPLE_FILES))
    finally:
        object.__setattr__(analyzer.settings, "openai_api_key", "")
    assert result["used_fallback"] is False
    assert result["summary"] == "Adds login rate limiting."
    assert [r["path"] for r in result["llm_risks"]] == ["src/auth/rate_limit.py"]  # invented path dropped


def test_fallback_groups_root_files():
    files = parse_files([{"filename": "README.md", "status": "modified", "additions": 1, "deletions": 0, "patch": ""}])
    assert fallback_groups(files)[0]["title"] == "Changes in (root)"
