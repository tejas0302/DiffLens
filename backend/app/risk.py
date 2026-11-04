"""Deterministic risk rules.

Why rules AND an LLM? Rules are fast, free, never hallucinate, and are easy
to unit-test. The LLM is good at understanding intent ("this refactors auth")
but can miss or invent things. We combine both: rules give a reliable floor,
the LLM adds judgment on top.
"""
import re

from .diff_parser import FileDiff

SENSITIVE_PATH = re.compile(
    r"(auth|login|session|token|password|permission|crypto|secret|payment|billing|security)",
    re.IGNORECASE,
)
DEPENDENCY_FILES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "pyproject.toml", "poetry.lock", "go.mod", "go.sum",
    "Cargo.toml", "Cargo.lock", "Gemfile", "Gemfile.lock",
}
MIGRATION_PATH = re.compile(r"(migrations?/|alembic/|\.sql$)", re.IGNORECASE)
CONFIG_PATH = re.compile(r"(\.github/workflows/|Dockerfile|docker-compose|\.env|\.ya?ml$)", re.IGNORECASE)
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec)/|(_test|\.test|\.spec|test_)", re.IGNORECASE)
# Looks like a hard-coded secret, e.g. API_KEY = "sk-abc123..."
SECRET_VALUE = re.compile(
    r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]",
    re.IGNORECASE,
)
DEBUG_LEFTOVER = re.compile(r"(console\.log\(|\bprint\(|debugger;|breakpoint\(\)|TODO|FIXME)")

LARGE_FILE_CHANGE = 400


def _flag(severity: str, kind: str, path: str, message: str) -> dict:
    return {"severity": severity, "kind": kind, "path": path, "message": message, "source": "rule"}


def is_test_file(path: str) -> bool:
    return bool(TEST_PATH.search(path))


def find_risks(files: list[FileDiff]) -> list[dict]:
    flags: list[dict] = []
    source_changed = False
    tests_changed = False

    for f in files:
        name = f.path.rsplit("/", 1)[-1]
        if is_test_file(f.path):
            tests_changed = True
        elif f.path.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs", ".rb")):
            source_changed = True

        if any(SECRET_VALUE.search(line) for line in f.added_lines):
            flags.append(_flag("high", "secret", f.path, "Possible hard-coded secret in added lines."))
        if SENSITIVE_PATH.search(f.path) and not is_test_file(f.path):
            flags.append(_flag("high", "security", f.path, "Touches security-sensitive code (auth/session/payment)."))
        if MIGRATION_PATH.search(f.path):
            flags.append(_flag("high", "migration", f.path, "Database migration: check it is reversible and safe on live data."))
        if name in DEPENDENCY_FILES:
            flags.append(_flag("medium", "dependency", f.path, "Dependency change: check versions and licenses."))
        if CONFIG_PATH.search(f.path):
            flags.append(_flag("medium", "config", f.path, "CI / deployment / config change."))
        if f.status == "removed":
            flags.append(_flag("medium", "deletion", f.path, "File deleted: check nothing still imports it."))
        if f.additions + f.deletions >= LARGE_FILE_CHANGE:
            flags.append(_flag("medium", "large_change", f.path,
                               f"Large change ({f.additions + f.deletions} lines): hard to review in one pass."))
        if f.patch == "" and f.status != "removed":
            flags.append(_flag("low", "no_patch", f.path, "Binary or too-large file: diff not shown by GitHub."))
        debug_hits = sum(1 for line in f.added_lines if DEBUG_LEFTOVER.search(line))
        if debug_hits and not is_test_file(f.path):
            flags.append(_flag("low", "debug_leftover", f.path,
                               f"{debug_hits} added line(s) look like debug output or TODOs."))

    if source_changed and not tests_changed:
        flags.append(_flag("medium", "missing_tests", "", "Source code changed but no test files were touched."))

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(flags, key=lambda x: order[x["severity"]])
