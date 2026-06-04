"""Bucket sandbox compat-sweep failures into named categories.

Pairs with ``run_compat_full.py``. The runner dumps a per-test traceback
into ``$SANDBOX_ERRORS_DIR/<integration>/<path>__<name>.txt``; this
script walks that tree, runs each file through an ordered list of
signature matchers, and writes:

- ``BACKLOG_FAILURES.json`` — machine-readable rollup
  (``{bucket → {integration → [test_node, …]}}``) for downstream tooling.
- A short stdout summary suitable for `tee`-ing onto an issue.

Categories are
ordered most-specific → most-generic; the first match wins, so unknown
genuinely means "no rule fired". A "≥95% of failures buckets out of
``unknown``" smoke gate lives at the bottom of the run; if that fails,
add more rules and re-run.

Usage::

    cd sandbox
    # After run_compat_full.py finishes:
    uv run python categorize_failures.py

    # Or against a custom errors dir:
    uv run python categorize_failures.py --errors-dir /tmp/sandbox_errors

The rules are intentionally regex-based on the per-test traceback excerpt
(JUnit's ``<failure>`` text + the ``--tb=short`` body). They're meant to
be cheap to extend — every rule is "if regex matches, bucket name" — so
adding a new category as failure shapes appear is one tuple entry.
"""

# Standalone CLI driver. Same Ruff carve-out as ``run_compat_full.py``.
# ruff: noqa: INP001, T201, S108

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re

_HERE = Path(__file__).resolve().parent
DEFAULT_ERRORS_DIR = Path(
    os.environ.get("SANDBOX_ERRORS_DIR", "/tmp/sandbox_errors")
)
DEFAULT_BACKLOG_JSON = _HERE / "BACKLOG_FAILURES.json"


@dataclass(frozen=True)
class Rule:
    """One signature rule: name + compiled regex pattern."""

    bucket: str
    pattern: re.Pattern[str]


# Order matters — first hit wins. Specific signatures (test-only autotag
# noise, named protocol gaps) sit above generic catch-alls. Patterns are
# compiled with ``re.IGNORECASE | re.DOTALL`` for resilience.
def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


RULES: tuple[Rule, ...] = (
    # ---- test-only -------------------------------------------------------
    # The autotag patch mutates entry.data; tests that assert
    # ``entry.data == <anything>`` or snapshot it see the new
    # ``__sandbox_group`` key. Same root cause whether it surfaces in an
    # `assert`, a `mappingproxy(...)` repr (pytest truncates the diff into
    # the JUnit `message` attribute and the visible slice often omits the
    # tag itself), or a Syrupy snapshot diff.
    Rule("test-only", _compile(r"__sandbox_group")),
    Rule("test-only", _compile(r"mappingproxy\(.+?'built-in'")),
    Rule("test-only", _compile(r"mappingproxy\(.+?'custom'")),
    # The autotag is the only thing that injects the literal value
    # ``'built-in'`` into a config-entry data assertion's diff.
    Rule("test-only", _compile(r"'built-in'.*?(==|expected|snapshot)")),
    # A `+ '__sandbox_group'` in a Syrupy diff is unambiguously the
    # autotag.
    Rule("test-only", _compile(r"\+\s+'__sandbox_group'")),
    # Catch-all for the `assert <something>.data == <literal>` shape.
    # `entry.data` is always a `MappingProxyType`; the only time the
    # assertion fails is when an extra key was added — and the only
    # extra-key source the compat lane adds is the autotag.
    Rule(
        "test-only",
        _compile(r"assert\s+mappingproxy\(.+?\)\s*==\s*[\{\[]"),
    ),
    # Diagnostic snapshots that include the entry's
    # full ``as_dict()`` now see a top-level ``+ 'sandbox': '<group>'``
    # line in the diff. Same root cause as ``__sandbox_group`` — the
    # autotag synthesises the field for compat coverage, the snapshot
    # was captured pre-autotag. Fix: refresh the snapshot in the
    # integration's test tree (out of sandbox scope).
    Rule("test-only", _compile(r"\+\s+'sandbox'\s*:\s*'(?:built-in|custom|main)'")),
    # Snapshot drift on ``'created_at'`` / ``'modified_at'``: tests that
    # didn't pin the wall clock with freezegun, so the snapshot's
    # baked-in timestamp doesn't match the new run's. Environmental,
    # not a sandbox bridge issue; fix is for the integration's test to use
    # ``@pytest.mark.freeze_time``. Matches both Syrupy diff form
    # (``+ 'created_at': ...``) and pytest dict-diff form
    # (``'created_at': '<iso>', 'data': ...``).
    Rule(
        "test-only",
        _compile(r"'(?:created_at|modified_at)'\s*:\s*'?\d{4}-\d{2}-\d{2}T"),
    ),

    # ---- proxy-missing ---------------------------------------------------
    Rule("proxy-missing", _compile(r"KeyError.*?_DOMAIN_PROXIES")),
    Rule("proxy-missing", _compile(r"no proxy (class )?for domain")),
    Rule("proxy-missing", _compile(r"unknown sandbox entity domain")),
    # Bridge gap: integration registers an entity in the sandbox but it
    # never shows up in main's entity registry. `proxy-missing` reuses
    # this bucket since the fix story is the same — make the bridge
    # surface the entity to main.
    Rule(
        "proxy-missing",
        _compile(r"async_is_registered.+?\n.*?AssertionError.*?False"),
    ),
    # Same root cause as the registry case: an integration that runs in
    # the sandbox registers an entity, but main's state machine never
    # sees it — `hass.states.get(...)` returns None.
    Rule(
        "proxy-missing",
        _compile(
            r"hass\.states\.get\(.+?\)\.state.+?\n.*?AttributeError.+?NoneType"
        ),
    ),

    # ---- protocol gaps ---------------------------------------------------
    # data_schema serialisation drift. The bridge does voluptuous-serialize
    # round-tripping; a regression would surface as None / wrong type.
    Rule(
        "data-schema-stripped",
        _compile(r"data_schema.*?(is None|None type|stripped|missing)"),
    ),
    Rule(
        "data-schema-stripped",
        _compile(r"FlowResult.*?data_schema.*?None"),
    ),
    Rule(
        "service-schema-missing",
        _compile(r"hass\.services\.async_register.*?schema"),
    ),
    Rule(
        "service-schema-missing",
        _compile(r"ServiceValidationError.*?bridge"),
    ),
    # Be conservative — `unique_id=None` shows up incidentally in many
    # `ConfigEntry` reprs, so only match assertions where the line in
    # question is *about* unique_id, not where it merely mentions one.
    Rule(
        "unique-id-not-propagated",
        _compile(r"assert\s+[^=]+unique_id[^=]*?(==|is)"),
    ),
    Rule(
        "unique-id-not-propagated",
        _compile(r"AssertionError.+?unique_id\s+(does not match|mismatch)"),
    ),

    # ---- restore_state ---------------------------------------------------
    Rule(
        "restore-state-not-applied",
        _compile(r"async_get_last_state.*?(None|missing|not restored)"),
    ),
    Rule(
        "restore-state-not-applied",
        _compile(r"restore.*?state.*?did not survive"),
    ),

    # ---- context propagation --------------------------------------------
    Rule("context-not-propagated", _compile(r"context\.user_id\b")),
    Rule("context-not-propagated", _compile(r"context\.parent_id\b")),
    Rule("context-not-propagated", _compile(r"Context\(.*?user_id=.+?\).*?==")),

    # ---- channel / re-entrancy ------------------------------------------
    Rule(
        "re-entrant-channel",
        _compile(r"sandbox.*?channel\.call.*?(deadlock|timeout|never returned)"),
    ),
    Rule(
        "re-entrant-channel",
        _compile(r"TimeoutError.*?sandbox.*?call"),
    ),

    # ---- store ----------------------------------------------------------
    Rule("store-key-rejected", _compile(r"_require_key.*?invalid")),
    Rule("store-key-rejected", _compile(r"sandbox.*?store.*?(rejected|invalid key)")),

    # ---- flow / async ---------------------------------------------------
    Rule(
        "flow-step-not-async",
        _compile(r"RuntimeWarning.*?coroutine.*?async_step_"),
    ),
    Rule("flow-step-not-async", _compile(r"async_step_.*?never awaited")),

    # ---- platform deny-list ---------------------------------------------
    Rule(
        "integration-uses-deny-listed-platform",
        _compile(r"sandbox.*?incompatible platform|deny-list.*?platform"),
    ),

    # ---- non-idempotent service handlers --------------------------------
    Rule(
        "non-idempotent-service-handler",
        _compile(r"_resolve_attachments|service handler.*?pre-?dispatch"),
    ),

    # ---- dependencies-not-shared ----------------------------------------
    Rule(
        "dependencies-not-shared",
        _compile(r"state for .+? not found.*?sandbox"),
    ),
    Rule(
        "dependencies-not-shared",
        _compile(r"main-side .+? not available to sandbox"),
    ),
    # An integration test mocks a dependency (HTTP client, websocket, …)
    # in the main process, but the sandbox runs in a separate process and
    # never sees the mock — setup fails with SETUP_ERROR / SETUP_RETRY.
    # Same root cause as the explicit "share state" patterns above.
    Rule(
        "dependencies-not-shared",
        _compile(
            r"ConfigEntryState\.SETUP_ERROR.+?is\s+"
            r"<?ConfigEntryState\.LOADED",
        ),
    ),
    Rule(
        "dependencies-not-shared",
        _compile(
            r"ConfigEntryState\.SETUP_ERROR.+?is\s+"
            r"<?ConfigEntryState\.SETUP_RETRY",
        ),
    ),
    Rule(
        "dependencies-not-shared",
        _compile(r"failed on setup with .+?ConfigEntryState\.SETUP_ERROR"),
    ),
)


def _load_traceback(path: Path) -> str:
    """Return the contents of a per-test error dump (utf-8, lossy)."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def categorise(traceback: str) -> str:
    """Match ``traceback`` against the rule list and return the bucket name."""
    for rule in RULES:
        if rule.pattern.search(traceback):
            return rule.bucket
    return "unknown"


def walk_errors(errors_dir: Path) -> dict[str, dict[str, list[tuple[str, str]]]]:
    """Walk per-integration error dumps; return ``{bucket → {domain → [(node, excerpt)]}}``."""
    out: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    if not errors_dir.is_dir():
        return out
    for integration_dir in sorted(errors_dir.iterdir()):
        # The per-integration log lives at ``<errors_dir>/<integration>.log``
        # alongside its sibling directory. JUnit XML lives in ``_junit/``;
        # skip both — they aren't per-test failure dumps.
        if not integration_dir.is_dir():
            continue
        if integration_dir.name.startswith("_"):
            continue
        for traceback_file in sorted(integration_dir.rglob("*.txt")):
            text = _load_traceback(traceback_file)
            if not text:
                continue
            node_id = _extract_node_id(text, traceback_file)
            excerpt = _short_excerpt(text)
            bucket = categorise(text)
            out[bucket][integration_dir.name].append((node_id, excerpt))
    return out


_NODE_LINE = re.compile(r"^node_id:\s*(.+)$", re.MULTILINE)


def _extract_node_id(text: str, path: Path) -> str:
    """Pull the ``node_id`` header from a dump; fall back to the file stem."""
    if (match := _NODE_LINE.search(text)) is not None:
        return match.group(1).strip()
    return path.stem


def _short_excerpt(text: str, *, lines: int = 6) -> str:
    """Return the first ``lines`` lines after the header so backlog entries stay terse."""
    body = text.split("\n", maxsplit=4)[-1] if "\n" in text else text
    return "\n".join(body.splitlines()[:lines])


def render_summary(
    buckets: dict[str, dict[str, list[tuple[str, str]]]],
) -> list[str]:
    """Render a stdout-friendly summary block."""
    total_failures = sum(
        len(node_list)
        for integrations in buckets.values()
        for node_list in integrations.values()
    )
    lines = [
        "Failure categorisation",
        "-" * 32,
        f"Total failures bucketed: {total_failures}",
        "",
        "Per-bucket counts (most → least):",
    ]
    per_bucket = sorted(
        (
            (
                bucket,
                sum(len(nodes) for nodes in integrations.values()),
                len(integrations),
            )
            for bucket, integrations in buckets.items()
        ),
        key=lambda r: (-r[1], r[0]),
    )
    for bucket, count, integration_count in per_bucket:
        lines.append(
            f"  {bucket:<40} {count:>5} failures across {integration_count:>3} integrations"
        )
    unknown_count = next(
        (count for bucket, count, _ in per_bucket if bucket == "unknown"),
        0,
    )
    if total_failures:
        ratio = (total_failures - unknown_count) / total_failures
        lines.append("")
        lines.append(
            f"Categorisation hit rate: {ratio:.1%}"
            f"  (target ≥95%; unknown bucket = {unknown_count})"
        )
    return lines


def serialise_buckets(
    buckets: dict[str, dict[str, list[tuple[str, str]]]],
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Convert tuples to plain dicts for JSON output."""
    return {
        bucket: {
            integration: [
                {"node_id": node, "excerpt": excerpt}
                for node, excerpt in items
            ]
            for integration, items in integrations.items()
        }
        for bucket, integrations in buckets.items()
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--errors-dir", type=Path, default=DEFAULT_ERRORS_DIR,
        help=("Per-test error dump root "
              "(default: $SANDBOX_ERRORS_DIR or /tmp/sandbox_errors)."),
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_BACKLOG_JSON,
        help="Where to write the bucket → integration → nodes JSON rollup.",
    )
    args = parser.parse_args(argv)

    buckets = walk_errors(args.errors_dir)
    args.out.write_text(json.dumps(serialise_buckets(buckets), indent=2, sort_keys=True))
    print("\n".join(render_summary(buckets)))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
