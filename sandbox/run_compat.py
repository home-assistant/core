"""Run HA Core integration test suites through the sandbox plugin.

Drives pytest with ``-p hass_client.testing.pytest_plugin`` (in-process)
or ``-p hass_client.testing.conftest_sandbox`` (subprocess) across the
``tests/components/<integration>/`` directory of every integration the
runner is asked about, parses the pytest summary, and writes a CSV plus
a short Markdown report into ``sandbox/``.

Shape mirrors ``sandbox/run_all_sandbox_tests.py`` (v1) but the report
location is local to ``sandbox/`` so the two compat lanes don't fight
over the same artefacts.

Usage::

    cd sandbox
    python run_compat.py                      # full run, in-process plugin
    python run_compat.py --plugin subprocess  # use the real-subprocess lane
    python run_compat.py input_boolean light  # restrict to specific integrations
"""

# This is a stand-alone CLI driver, not a Python package module — the
# ruff rules around implicit namespace packages, ``print`` for status,
# and ``/tmp`` fallback for the per-integration error dump don't apply.
# ruff: noqa: INP001, T201, S108, PERF401

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
import time

# Paths are relative to this script (sandbox/run_compat.py).
_HERE = Path(__file__).resolve().parent
CORE_ROOT = _HERE.parent
CORE_TESTS_DIR = CORE_ROOT / "tests" / "components"
HASS_CLIENT_DIR = _HERE / "hass_client"
DEFAULT_RESULTS_CSV = _HERE / "COMPAT.csv"
# COMPAT.md is the curated baseline report and is NOT overwritten
# on every run. Auto-generated runs land in COMPAT_LATEST.md so reviewers
# can diff against the curated baseline.
DEFAULT_REPORT_MD = _HERE / "COMPAT_LATEST.md"
ERRORS_DIR = Path(os.environ.get("SANDBOX_ERRORS_DIR", "/tmp/sandbox_errors"))

# Map CLI plugin choice → pytest ``-p`` argument.
PLUGINS = {
    "inprocess": "hass_client.testing.pytest_plugin",
    "subprocess": "hass_client.testing.conftest_sandbox",
}

_SUMMARY_RE = {
    "passed": re.compile(r"(\d+) passed"),
    "failed": re.compile(r"(\d+) failed"),
    "errors": re.compile(r"(\d+) error"),
    "skipped": re.compile(r"(\d+) skipped"),
}

_ENGAGED_RE = re.compile(
    r"sandbox-compat: router entry_setup engaged (\d+) time\(s\),"
    r" (\d+) entries tagged"
)


@dataclass
class Result:
    """Single-integration pytest run summary."""

    integration: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    engaged: int = 0
    tagged: int = 0
    status: str = "no_tests"

    @property
    def total(self) -> int:
        """Total tests collected and run for this integration."""
        return self.passed + self.failed + self.errors + self.skipped


def discover_integrations() -> list[str]:
    """Return every component dir under ``tests/components`` that has tests."""
    integrations: list[str] = []
    for entry in sorted(CORE_TESTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if any(p.name.startswith("test_") and p.suffix == ".py" for p in entry.iterdir()):
            integrations.append(entry.name)
    return integrations


def run_one(integration: str, plugin: str, *, timeout: float = 300.0) -> Result:
    """Run pytest against one integration's test directory."""
    test_dir = CORE_TESTS_DIR / integration
    result = Result(integration=integration)
    try:
        proc = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "pytest",
                "-p",
                plugin,
                str(test_dir),
                "--tb=no",
                "-q",
                "--no-header",
                "--no-cov",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            # Core env has every test dep (freezegun, pytest-aiohttp, …);
            # the hass_client env is intentionally minimal and can't load
            # ``tests/conftest.py``.
            cwd=CORE_ROOT,
            check=False,
        )
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        result.status = "timeout"
        ERRORS_DIR.mkdir(parents=True, exist_ok=True)
        (ERRORS_DIR / f"{integration}.txt").write_text(
            f"timed out after {timeout:.0f}s\n"
        )
        return result

    for line in output.splitlines()[-10:]:
        for field, pattern in _SUMMARY_RE.items():
            if (match := pattern.search(line)) is not None:
                setattr(result, field, int(match.group(1)))
    if (match := _ENGAGED_RE.search(output)) is not None:
        result.engaged = int(match.group(1))
        result.tagged = int(match.group(2))

    if result.total == 0:
        result.status = "no_tests"
    elif result.failed != 0 or result.errors != 0:
        result.status = "issues"
    elif result.tagged == 0:
        # The integration classifies to main (camera/tts/system/ALWAYS_MAIN)
        # — vanilla behavior is the correct measurement here.
        result.status = "main"
    elif result.engaged == 0 and result.passed > 0:
        # Entries were tagged for a sandbox but nothing ever routed — the
        # plugin regressed to a no-op; do NOT report this as compatibility.
        result.status = "no_op"
    else:
        result.status = "pass"

    if result.status in ("issues", "timeout"):
        ERRORS_DIR.mkdir(parents=True, exist_ok=True)
        (ERRORS_DIR / f"{integration}.txt").write_text(output)
    return result


def write_csv(results: list[Result], path: Path) -> None:
    """Persist per-integration results as CSV."""
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["integration", "status", "passed", "failed", "errors", "skipped", "engaged"]
        )
        for result in results:
            writer.writerow(
                [
                    result.integration,
                    result.status,
                    result.passed,
                    result.failed,
                    result.errors,
                    result.skipped,
                    result.engaged,
                ]
            )


def write_report(results: list[Result], plugin: str, path: Path) -> None:
    """Write a short Markdown summary suitable for review."""
    counts: dict[str, int] = {
        "pass": 0,
        "main": 0,
        "issues": 0,
        "timeout": 0,
        "no_tests": 0,
        "no_op": 0,
    }
    totals = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
        totals["passed"] += result.passed
        totals["failed"] += result.failed
        totals["errors"] += result.errors
        totals["skipped"] += result.skipped

    lines = [
        "# Sandbox compat report",
        "",
        f"Plugin: `{plugin}`",
        "",
        "## Summary",
        "",
        f"- Integrations passing (sandboxed): **{counts.get('pass', 0)}**",
        f"- Integrations on main by classification: **{counts.get('main', 0)}**",
        f"- Integrations with issues: **{counts.get('issues', 0)}**",
        f"- No-op runs (sandbox never engaged): **{counts.get('no_op', 0)}**",
        f"- Timeouts: **{counts.get('timeout', 0)}**",
        f"- No tests collected: **{counts.get('no_tests', 0)}**",
        "",
        f"- Tests passed: **{totals['passed']}**",
        f"- Tests failed: **{totals['failed']}**",
        f"- Test errors: **{totals['errors']}**",
        f"- Tests skipped: **{totals['skipped']}**",
        "",
        "## Per-integration results",
        "",
        "| integration | status | passed | failed | errors | skipped | engaged |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            f"| {result.integration} | {result.status} | {result.passed} |"
            f" {result.failed} | {result.errors} | {result.skipped} |"
            f" {result.engaged} |"
        )
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run the compat lane and write the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "integrations",
        nargs="*",
        help="Specific integration names. Defaults to every component with tests.",
    )
    parser.add_argument(
        "--plugin",
        choices=sorted(PLUGINS),
        default="inprocess",
        help="Which sandbox plugin to drive (default: inprocess).",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help=(
            "Concurrent pytest subprocesses (default: 1). Each runs one"
            " integration's suite; 4-8 is reasonable on a workstation."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Per-integration timeout in seconds (default: 300).",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_RESULTS_CSV,
        help="Where to write the per-integration CSV.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_MD,
        help="Where to write the Markdown report.",
    )
    args = parser.parse_args(argv)

    plugin = PLUGINS[args.plugin]
    integrations = args.integrations or discover_integrations()
    total = len(integrations)
    if total == 0:
        print("No integrations to run.", file=sys.stderr)
        return 1

    start = time.monotonic()
    results: list[Result] = []
    # Results in input order regardless of completion order; progress prints
    # as each integration finishes.
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [
            pool.submit(run_one, integration, plugin, timeout=args.timeout)
            for integration in integrations
        ]
        by_future = dict(zip(futures, integrations, strict=True))
        for done, future in enumerate(futures, 1):
            result = future.result()
            results.append(result)
            elapsed = time.monotonic() - start
            rate = done / elapsed if elapsed > 0 else 0
            eta_minutes = (total - done) / rate / 60 if rate else 0
            print(
                f"[{done}/{total}] {by_future[future]} -> {result.status}"
                f" ({result.passed}p/{result.failed}f/{result.errors}e/{result.skipped}s)"
                f" | ETA: {eta_minutes:.0f}m",
                flush=True,
            )

    write_csv(results, args.csv)
    write_report(results, plugin, args.report)
    print(f"\nWrote {args.csv}")
    print(f"Wrote {args.report}")

    if results and all(
        result.engaged == 0 for result in results if result.tagged
    ) and any(result.tagged for result in results):
        print(
            "ERROR: no test in the entire run routed an entry through a"
            " sandbox — the compat lane is a no-op.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
