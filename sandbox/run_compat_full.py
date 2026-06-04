"""Run the full sandbox compat sweep across every routable integration.

This sweep broadens the 37-integration baseline to cover
**every config-entry-based integration** that the sandbox classifier would
route to a sandbox. The goal of this run is not to fix anything — it is
to *measure* and *categorize* so the resulting backlog is grounded in real
data.

Discovery rules (see ``discover_integrations``):

- Walk ``homeassistant/components/``.
- Skip ``integration_type`` ``virtual`` or ``system`` (no runtime to
  sandbox).
- Skip the ``ALWAYS_MAIN`` set (decided by the classifier already).
- Skip integrations whose ``manifest.json`` has ``config_flow: false``
  (YAML-only integrations are out of scope).
- Skip integrations whose ``tests/components/<domain>/`` directory has no
  ``test_*.py`` files (no signal either way).
- Skip integrations whose source ships a platform file in
  ``SANDBOX_INCOMPATIBLE_PLATFORMS`` (classifier would route them to main,
  so the sweep wouldn't be measuring the bridge).

For every surviving integration the runner spawns a pytest subprocess with
``-p hass_client.testing.pytest_plugin`` (the in-process plugin used by
the baseline), captures the JUnit XML output, and dumps the full
text output + per-test failure tracebacks into the per-integration error
directory so the categorizer (``categorize_failures.py``) can bucket
every failure.

Outer concurrency comes from asyncio + a semaphore: by default four
integrations run in parallel. Per-integration parallelism via
``pytest-xdist`` ``-n auto`` is opt-in (``--xdist``) because the
``xdist`` worker spin-up cost dominates for small integrations and the
outer concurrency already keeps the box busy.

Usage::

    cd sandbox
    # Full sweep (every classifier-routable integration)
    uv run python run_compat_full.py

    # Restrict to a list (handy for iterating on the categorizer)
    uv run python run_compat_full.py input_boolean light switch

    # Validation: re-run the 37-integration baseline
    uv run python run_compat_full.py --baseline-37

The two committed deliverables are written at the end:

- ``COMPAT_FULL.md`` — per-integration results table + sweep header.
- ``COMPAT_FULL.csv`` — machine-readable version of the same table.
"""

# Standalone CLI driver, not a package module — Ruff's package-naming /
# print-for-status / /tmp-fallback rules don't apply here, same as
# ``run_compat.py``.
# ruff: noqa: INP001, T201, S108, PERF401

import argparse
import asyncio
import csv as csv_module
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import time
from xml.etree.ElementTree import ParseError, parse as et_parse

# Paths are relative to this script (sandbox/run_compat_full.py).
_HERE = Path(__file__).resolve().parent
CORE_ROOT = _HERE.parent
COMPONENTS_DIR = CORE_ROOT / "homeassistant" / "components"
CORE_TESTS_DIR = CORE_ROOT / "tests" / "components"
DEFAULT_CSV = _HERE / "COMPAT_FULL.csv"
DEFAULT_REPORT_MD = _HERE / "COMPAT_FULL.md"
ERRORS_DIR = Path(os.environ.get("SANDBOX_ERRORS_DIR", "/tmp/sandbox_errors"))

# Mirrors homeassistant/components/sandbox/const.py. Duplicated here
# because importing the live module would require booting the core test
# env from this stand-alone driver. The unit tests guard against
# behavioural drift; the per-integration sweep is allowed to lag by an
# entry — if either set changes, update both copies and re-run.
ALWAYS_MAIN: frozenset[str] = frozenset(
    {"script", "automation", "scene", "cloud", "ai_task", "image"}
)
SANDBOX_INCOMPATIBLE_PLATFORMS: frozenset[str] = frozenset(
    {"stt", "tts", "conversation", "assist_satellite", "wake_word", "camera"}
)

# The 37-integration baseline list, for the ``--baseline-37`` shortcut. The
# list lives both here and in ``COMPAT.md``; keep them in sync.
BASELINE_37: tuple[str, ...] = (
    "input_boolean", "input_button", "input_datetime", "input_number",
    "input_select", "input_text", "counter", "timer", "schedule", "zone",
    "tag", "group", "person", "scene", "todo", "automation", "script",
    "alert", "template", "plant", "proximity", "min_max", "statistics",
    "utility_meter", "derivative", "integration", "generic_thermostat",
    "generic_hygrostat", "history_stats", "threshold", "filter",
    "mqtt_statestream", "recorder", "rest", "logbook", "command_line",
    "trend",
)


@dataclass
class Result:
    """Single-integration pytest-run summary."""

    integration: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration: float = 0.0
    status: str = "no_tests"
    failure_signatures: list[str] = field(default_factory=list)
    dominant_bucket: str | None = None

    @property
    def total(self) -> int:
        """Total tests collected and run for this integration."""
        return self.passed + self.failed + self.errors + self.skipped


def _has_test_files(test_dir: Path) -> bool:
    """Return True if ``test_dir`` ships at least one ``test_*.py``."""
    if not test_dir.is_dir():
        return False
    return any(
        p.name.startswith("test_") and p.suffix == ".py"
        for p in test_dir.iterdir()
    )


def _ships_incompatible_platform(component_dir: Path) -> bool:
    """Return True if ``component_dir`` has a platform in the deny-list."""
    return any(
        (component_dir / f"{plat}.py").exists()
        for plat in SANDBOX_INCOMPATIBLE_PLATFORMS
    )


def discover_integrations() -> tuple[list[str], dict[str, int]]:
    """Return the (sorted) eligible integration names and filter stats."""
    stats: dict[str, int] = {
        "no_manifest": 0,
        "virtual_or_system": 0,
        "always_main": 0,
        "incompatible_platform": 0,
        "no_config_flow": 0,
        "no_tests": 0,
        "eligible": 0,
    }
    eligible: list[str] = []
    for component in sorted(COMPONENTS_DIR.iterdir()):
        if not component.is_dir():
            continue
        manifest_path = component / "manifest.json"
        if not manifest_path.exists():
            stats["no_manifest"] += 1
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            stats["no_manifest"] += 1
            continue
        itype = manifest.get("integration_type", "hub")
        if itype in ("virtual", "system"):
            stats["virtual_or_system"] += 1
            continue
        if component.name in ALWAYS_MAIN:
            stats["always_main"] += 1
            continue
        if _ships_incompatible_platform(component):
            stats["incompatible_platform"] += 1
            continue
        if not manifest.get("config_flow", False):
            stats["no_config_flow"] += 1
            continue
        if not _has_test_files(CORE_TESTS_DIR / component.name):
            stats["no_tests"] += 1
            continue
        eligible.append(component.name)
        stats["eligible"] += 1
    return eligible, stats


def _parse_junit(xml_path: Path, *, errors_dir: Path, integration: str) -> Result:
    """Parse a JUnit XML report into a ``Result`` + per-test traceback dump."""
    result = Result(integration=integration)
    try:
        # XML is produced by pytest's own --junit-xml in the same
        # subprocess we control — not untrusted input. S314 carve-out.
        tree = et_parse(xml_path)  # noqa: S314
    except (ParseError, FileNotFoundError):
        result.status = "no_tests"
        return result
    root = tree.getroot()
    # JUnit format: <testsuites><testsuite ...><testcase .../></testsuite></testsuites>
    suite = root[0] if len(root) > 0 else None
    if suite is None or suite.tag != "testsuite":
        return result

    result.passed = int(suite.attrib.get("tests", 0))
    result.failed = int(suite.attrib.get("failures", 0))
    result.errors = int(suite.attrib.get("errors", 0))
    result.skipped = int(suite.attrib.get("skipped", 0))
    result.duration = float(suite.attrib.get("time", 0.0))
    # JUnit's ``tests`` counts every test including failures/errors/skipped.
    # Re-derive ``passed`` so the dataclass meaning matches the baseline CSV.
    result.passed = max(0, result.passed - result.failed - result.errors - result.skipped)

    integration_errors_dir = errors_dir / integration
    if integration_errors_dir.exists():
        shutil.rmtree(integration_errors_dir)

    for testcase in suite:
        if testcase.tag != "testcase":
            continue
        failure_node = None
        for child in testcase:
            if child.tag in ("failure", "error"):
                failure_node = child
                break
        if failure_node is None:
            continue
        integration_errors_dir.mkdir(parents=True, exist_ok=True)
        classname = testcase.attrib.get("classname", "unknown").replace(".", "/")
        # Best-effort filename: ``<classname>::<name>`` with characters that
        # are awkward in a filename replaced by underscores. The dot→slash
        # swap on classname keeps the path layout close to the on-disk test
        # tree so reviewers can find the originating file quickly.
        name = testcase.attrib.get("name", "unknown")
        safe_name = "".join(
            c if c.isalnum() or c in "_.-[]" else "_" for c in name
        )
        node_path = integration_errors_dir / f"{classname}__{safe_name}.txt"
        node_path.parent.mkdir(parents=True, exist_ok=True)
        body = [
            f"node_id: {testcase.attrib.get('classname', '')}::{name}",
            f"kind: {failure_node.tag}",
            f"message: {failure_node.attrib.get('message', '')}",
            "",
            failure_node.text or "",
        ]
        node_path.write_text("\n".join(body))
        # Cheap dominant-bucket hint: store the failure message so the
        # caller (and categorize_failures.py) can guess without re-reading.
        result.failure_signatures.append(failure_node.attrib.get("message", ""))

    if result.total == 0:
        result.status = "no_tests"
    elif result.failed == 0 and result.errors == 0:
        result.status = "pass"
    else:
        result.status = "issues"
    return result


async def run_one(
    integration: str,
    *,
    semaphore: asyncio.Semaphore,
    timeout: float,
    use_xdist: bool,
    errors_dir: Path,
    junit_dir: Path,
) -> Result:
    """Spawn pytest for one integration, parse JUnit, return a ``Result``."""
    test_dir = CORE_TESTS_DIR / integration
    junit_path = junit_dir / f"{integration}.xml"
    log_path = errors_dir / f"{integration}.log"
    cmd = [
        "uv", "run", "python", "-m", "pytest",
        "-p", "hass_client.testing.pytest_plugin",
        str(test_dir),
        "--tb=short", "-q", "--no-header", "--no-cov",
        f"--junit-xml={junit_path}",
    ]
    if use_xdist:
        cmd.extend(["-n", "auto"])

    async with semaphore:
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=CORE_ROOT,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError:
                proc.kill()
                await proc.wait()
                duration = time.monotonic() - start
                errors_dir.mkdir(parents=True, exist_ok=True)
                log_path.write_text(
                    f"timed out after {timeout:.0f}s\n"
                )
                return Result(
                    integration=integration, status="timeout", duration=duration
                )
        except (FileNotFoundError, PermissionError) as exc:
            errors_dir.mkdir(parents=True, exist_ok=True)
            log_path.write_text(f"failed to spawn pytest: {exc}\n")
            return Result(integration=integration, status="error", duration=0.0)

    duration = time.monotonic() - start
    output = stdout.decode("utf-8", errors="replace") if stdout else ""

    result = _parse_junit(junit_path, errors_dir=errors_dir, integration=integration)
    result.duration = duration

    if result.status in ("issues", "timeout") or result.total == 0:
        # Keep the full pytest output around for awkward-failure debugging
        # (e.g. collection errors that the JUnit report can't represent).
        errors_dir.mkdir(parents=True, exist_ok=True)
        log_path.write_text(output)
    return result


def write_csv(results: list[Result], path: Path) -> None:
    """Persist per-integration results in the same column order as COMPAT.csv."""
    with path.open("w", newline="") as fh:
        writer = csv_module.writer(fh)
        writer.writerow([
            "integration", "status", "passed", "failed", "errors", "skipped",
            "duration_s", "dominant_bucket",
        ])
        for result in results:
            writer.writerow([
                result.integration, result.status, result.passed, result.failed,
                result.errors, result.skipped, f"{result.duration:.2f}",
                result.dominant_bucket or "",
            ])


def write_report(
    results: list[Result],
    *,
    path: Path,
    discovery_stats: dict[str, int],
    started_at: datetime,
    finished_at: datetime,
    concurrency: int,
    use_xdist: bool,
) -> None:
    """Render the COMPAT_FULL.md report. See module docstring for shape."""
    counts: dict[str, int] = {"pass": 0, "issues": 0, "timeout": 0, "no_tests": 0, "error": 0}
    totals = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
        totals["passed"] += result.passed
        totals["failed"] += result.failed
        totals["errors"] += result.errors
        totals["skipped"] += result.skipped

    test_total = totals["passed"] + totals["failed"] + totals["errors"]
    pass_rate = (totals["passed"] / test_total * 100.0) if test_total else 0.0
    integration_total = len(results)
    integration_pass_rate = (
        counts.get("pass", 0) / integration_total * 100.0
        if integration_total else 0.0
    )

    lines: list[str] = [
        "# Sandbox — full compat sweep",
        "",
        "**This file is auto-generated by `run_compat_full.py`** — re-run the",
        "script to refresh it. Companion machine-readable CSV is `COMPAT_FULL.csv`,",
        "categorised remediation backlog is `BACKLOG.md`.",
        "",
        "## Sweep parameters",
        "",
        f"- Started:  `{started_at.isoformat(timespec='seconds')}`",
        f"- Finished: `{finished_at.isoformat(timespec='seconds')}`",
        f"- Wall time: **{(finished_at - started_at).total_seconds():.0f}s**",
        f"- Outer concurrency: **{concurrency}**",
        f"- Per-integration pytest-xdist: **{'on' if use_xdist else 'off'}**",
        "- Plugin: `hass_client.testing.pytest_plugin` (in-process)",
        "",
        "## Discovery",
        "",
        "Walked `homeassistant/components/`, applied the discovery filters:",
        "",
        "| Filter | Skipped |",
        "| --- | ---: |",
        f"| No / invalid manifest | {discovery_stats.get('no_manifest', 0)} |",
        f"| `integration_type` in (`virtual`, `system`) | {discovery_stats.get('virtual_or_system', 0)} |",
        f"| Domain in `ALWAYS_MAIN` | {discovery_stats.get('always_main', 0)} |",
        f"| Ships a platform in `SANDBOX_INCOMPATIBLE_PLATFORMS` | {discovery_stats.get('incompatible_platform', 0)} |",
        f"| No `config_flow` in manifest | {discovery_stats.get('no_config_flow', 0)} |",
        f"| No `test_*.py` files | {discovery_stats.get('no_tests', 0)} |",
        f"| **Eligible (this sweep)** | **{discovery_stats.get('eligible', 0)}** |",
        "",
        "## Summary",
        "",
        f"- Integrations exercised: **{integration_total}**",
        f"- Fully passing: **{counts.get('pass', 0)}** ({integration_pass_rate:.2f}%)",
        f"- With failures: **{counts.get('issues', 0)}**",
        f"- Timeouts: **{counts.get('timeout', 0)}**",
        f"- Spawn errors: **{counts.get('error', 0)}**",
        f"- No tests collected: **{counts.get('no_tests', 0)}**",
        "",
        f"- Tests passed: **{totals['passed']}**",
        f"- Tests failed: **{totals['failed']}**",
        f"- Test errors: **{totals['errors']}**",
        f"- Tests skipped: **{totals['skipped']}**",
        f"- **Test-level pass rate: {pass_rate:.2f}%**",
        "",
        "## Per-integration results",
        "",
        "| integration | status | passed | failed | errors | skipped | dur (s) | bucket |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in sorted(results, key=lambda r: r.integration):
        lines.append(
            f"| {result.integration} | {result.status} | {result.passed} | "
            f"{result.failed} | {result.errors} | {result.skipped} | "
            f"{result.duration:.1f} | {result.dominant_bucket or ''} |"
        )
    lines.append("")
    lines.append("Per-failure tracebacks are dumped under "
                 "`${SANDBOX_ERRORS_DIR:-/tmp/sandbox_errors}/<integration>/`.")
    path.write_text("\n".join(lines) + "\n")


async def _gather(
    integrations: list[str],
    *,
    concurrency: int,
    timeout: float,
    use_xdist: bool,
    errors_dir: Path,
    junit_dir: Path,
) -> list[Result]:
    """Run the per-integration pytest invocations with outer concurrency."""
    semaphore = asyncio.Semaphore(concurrency)
    results: list[Result] = []
    completed = 0
    total = len(integrations)
    start = time.monotonic()

    async def _run_and_log(integration: str) -> Result:
        nonlocal completed
        result = await run_one(
            integration,
            semaphore=semaphore,
            timeout=timeout,
            use_xdist=use_xdist,
            errors_dir=errors_dir,
            junit_dir=junit_dir,
        )
        completed += 1
        elapsed = time.monotonic() - start
        rate = completed / elapsed if elapsed > 0 else 0.0
        eta_min = (total - completed) / rate / 60 if rate else 0.0
        print(
            f"[{completed}/{total}] {integration} -> {result.status} "
            f"({result.passed}p/{result.failed}f/{result.errors}e/{result.skipped}s) "
            f"in {result.duration:.1f}s | ETA: {eta_min:.0f}m",
            flush=True,
        )
        return result

    tasks = [asyncio.create_task(_run_and_log(d)) for d in integrations]
    for task in asyncio.as_completed(tasks):
        results.append(await task)
    return results


def main(argv: list[str] | None = None) -> int:
    """Drive the full sweep."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "integrations",
        nargs="*",
        help=(
            "Specific integration names. Defaults to every classifier-routable"
            " integration discovered in `homeassistant/components/`."
        ),
    )
    parser.add_argument(
        "--baseline-37", action="store_true",
        help="Restrict to the 37-integration baseline list.",
    )
    parser.add_argument(
        "--concurrency", type=int, default=4,
        help="How many integrations to run in parallel (default: 4).",
    )
    parser.add_argument(
        "--timeout", type=float, default=300.0,
        help="Per-integration timeout in seconds (default: 300).",
    )
    parser.add_argument(
        "--xdist", action="store_true",
        help="Pass `-n auto` to per-integration pytest (default: off).",
    )
    parser.add_argument(
        "--csv", type=Path, default=DEFAULT_CSV,
        help="Where to write the per-integration CSV.",
    )
    parser.add_argument(
        "--report", type=Path, default=DEFAULT_REPORT_MD,
        help="Where to write the Markdown report.",
    )
    parser.add_argument(
        "--errors-dir", type=Path, default=ERRORS_DIR,
        help="Per-test error dump root (default: $SANDBOX_ERRORS_DIR or /tmp/sandbox_errors).",
    )
    parser.add_argument(
        "--junit-dir", type=Path, default=ERRORS_DIR / "_junit",
        help="Where to keep per-integration JUnit XML files.",
    )
    args = parser.parse_args(argv)

    args.errors_dir.mkdir(parents=True, exist_ok=True)
    args.junit_dir.mkdir(parents=True, exist_ok=True)

    if args.baseline_37 and args.integrations:
        print("--baseline-37 conflicts with explicit integrations.", file=sys.stderr)
        return 1
    if args.baseline_37:
        integrations = list(BASELINE_37)
        discovery_stats: dict[str, int] = {"eligible": len(integrations)}
    elif args.integrations:
        integrations = list(args.integrations)
        discovery_stats = {"eligible": len(integrations)}
    else:
        integrations, discovery_stats = discover_integrations()

    if not integrations:
        print("No integrations to run.", file=sys.stderr)
        return 1

    print(f"Running {len(integrations)} integrations "
          f"(concurrency={args.concurrency}, timeout={args.timeout:.0f}s, "
          f"xdist={'on' if args.xdist else 'off'})")

    started_at = datetime.now()
    results = asyncio.run(_gather(
        integrations,
        concurrency=args.concurrency,
        timeout=args.timeout,
        use_xdist=args.xdist,
        errors_dir=args.errors_dir,
        junit_dir=args.junit_dir,
    ))
    finished_at = datetime.now()
    results.sort(key=lambda r: r.integration)

    write_csv(results, args.csv)
    write_report(
        results,
        path=args.report,
        discovery_stats=discovery_stats,
        started_at=started_at,
        finished_at=finished_at,
        concurrency=args.concurrency,
        use_xdist=args.xdist,
    )
    print(f"\nWrote {args.csv}")
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
