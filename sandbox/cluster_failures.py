"""Cluster compat-lane failures into shared root-cause signatures.

Reads the per-integration error dumps run_compat.py writes for every
non-passing suite ($SANDBOX_ERRORS_DIR, default /tmp/sandbox_errors/).
Run the sweep with --tb=line (the default) so each failure line reads
  /abs/path.py:123: ExceptionType: message
Normalizes that into a "<ExceptionType> @ <frame>: <message>" signature
(noisy tokens — addresses, ULIDs, entity ids, numbers — masked) and
clusters across integrations. Writes clusters.md + clusters.json.

    python sandbox/cluster_failures.py sandbox/reports/<date>/clusters
"""

# Stand-alone CLI driver, not a package module — same carve-out as
# run_compat.py for implicit-namespace / print / tmp rules.
# ruff: noqa: INP001, T201, S108, D103

from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import re
import sys

SRC = Path(os.environ.get("SANDBOX_ERRORS_DIR", "/tmp/sandbox_errors"))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("clusters")

# --tb=line failure lines: /abs/path.py:123: ExceptionType: message
TBLINE = re.compile(r"^(/\S+?\.py):(\d+): (\S+?): (.*)$")

# Types reported in pytest's warnings summary, not test failures.
WARNING_TYPES = {
    "DeprecationWarning",
    "PendingDeprecationWarning",
    "UserWarning",
    "RuntimeWarning",
    "FutureWarning",
    "PytestUnraisableExceptionWarning",
    "PytestWarning",
    "PytestDeprecationWarning",
}

# order matters: most specific first. Keep human-meaningful words (enum
# names, states, attribute names); normalize only genuinely noisy tokens.
NORMALIZERS = [
    (re.compile(r" at 0x[0-9a-fA-F]+"), " at 0xADDR"),
    (re.compile(r"0x[0-9a-fA-F]+"), "0xADDR"),
    (re.compile(r"[0-9a-f]{32,}"), "HEXID"),
    (re.compile(r"[0-9A-HJKMNP-TV-Z]{26}"), "ULID"),
    # entity ids / unique ids: domain.object_id with digits or long tails
    (re.compile(r"\b[a-z_]+\.[a-z0-9_]{3,}\b"), "EID"),
    (re.compile(r"\b\d+\.\d+\b"), "N.N"),
    (re.compile(r"\b\d{2,}\b"), "N"),
    (re.compile(r"\s+"), " "),
]


def signature(reason: str) -> str:
    sig = reason.strip()
    sig = sig.removesuffix("...")
    for pat, repl in NORMALIZERS:
        sig = pat.sub(repl, sig)
    return sig.strip()[:220]


def main() -> None:
    clusters: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "integrations": Counter(), "examples": []}
    )
    per_file_lines: dict[str, list[str]] = {}
    timeouts = []
    for path in sorted(SRC.glob("*.txt")):
        integration = path.stem
        text = path.read_text(errors="replace")
        if text.startswith("timed out"):
            timeouts.append(integration)
            continue
        lines = []
        for line in text.splitlines():
            m = TBLINE.match(line.strip())
            if m is None:
                continue
            frame_path, _lineno, exc_type, reason = m.groups()
            if exc_type.rsplit(".", 1)[-1] in WARNING_TYPES:
                continue
            # Cluster on the raising frame's file (repo-relative), the
            # exception type, and the normalized message — the frame
            # separates "same message, different mechanism" cases.
            frame = frame_path.split("core-sandbox/")[-1]
            frame_key = frame if not frame.startswith("tests/") else "tests/<suite>"
            exc_short = exc_type.rsplit(".", 1)[-1]
            sig = f"{exc_short} @ {frame_key}: {signature(reason)}"
            c = clusters[sig]
            c["count"] += 1
            c["integrations"][integration] += 1
            if len(c["examples"]) < 5:
                c["examples"].append(f"{integration} {frame}: {reason[:220]}")
            lines.append(sig)
        per_file_lines[integration] = lines

    ranked = sorted(clusters.items(), key=lambda kv: -kv[1]["count"])
    OUT.mkdir(parents=True, exist_ok=True)

    # machine-readable full dump
    with (OUT / "clusters.json").open("w") as fh:
        json.dump(
            [
                {
                    "signature": sig,
                    "failures": c["count"],
                    "integration_count": len(c["integrations"]),
                    "integrations": dict(c["integrations"].most_common()),
                    "examples": c["examples"],
                }
                for sig, c in ranked
            ],
            fh,
            indent=1,
        )

    # human summary
    with (OUT / "clusters.md").open("w") as fh:
        total = sum(c["count"] for _, c in ranked)
        fh.write("# Compat failure clusters\n\n")
        fh.write(
            f"{total} FAILED/ERROR lines across {len(per_file_lines)} integrations; "
        )
        fh.write(f"{len(ranked)} distinct signatures; {len(timeouts)} timeouts.\n\n")
        fh.write("| # | failures | integrations | signature |\n|---:|---:|---:|---|\n")
        for i, (sig, c) in enumerate(ranked[:60], 1):
            fh.write(
                f"| {i} | {c['count']} | {len(c['integrations'])} | `{sig[:160]}` |\n"
            )
        fh.write("\n## Timeouts\n\n" + ", ".join(timeouts) + "\n")
        fh.write("\n## Examples for top 25\n\n")
        for i, (sig, c) in enumerate(ranked[:25], 1):
            fh.write(
                f"### {i}. `{sig[:160]}` — {c['count']} failures / {len(c['integrations'])} integrations\n\n"
            )
            tops = ", ".join(f"{k} ({v})" for k, v in c["integrations"].most_common(8))
            fh.write(f"Top integrations: {tops}\n\n")
            for ex in c["examples"][:3]:
                fh.write(f"- `{ex}`\n")
            fh.write("\n")

    print(
        f"{sum(c['count'] for _, c in ranked)} failure lines, {len(ranked)} signatures"
    )
    for i, (sig, c) in enumerate(ranked[:20], 1):
        print(
            f"{i:3d}. {c['count']:5d}x across {len(c['integrations']):4d} ints | {sig[:130]}"
        )


main()
