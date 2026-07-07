"""Render a draft ``BACKLOG.md`` from the categorizer's JSON rollup.

Pairs with ``categorize_failures.py``. Reads ``BACKLOG_FAILURES.json``
(``{bucket → {integration → [{node_id, excerpt}]}}``) and writes the
section-per-bucket Markdown the Phase 16 spec asks for.

The "Proposed fix" stub is intentionally left as a TODO marker per
section — that field needs human judgement (file paths, rough size,
complexity), and the sweep should produce the draft skeleton so the
backlog landing is reviewable without a 600-line Markdown blob in the
commit diff.

Usage::

    cd sandbox
    uv run python generate_backlog.py              # writes BACKLOG.md
    uv run python generate_backlog.py --out FOO.md # custom output path
"""

# ruff: noqa: INP001, T201

import argparse
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DEFAULT_BACKLOG_JSON = _HERE / "BACKLOG_FAILURES.json"
DEFAULT_BACKLOG_MD = _HERE / "BACKLOG.md"

# Per-bucket prose. Keeps the generator output reviewable by anchoring
# each section to a one-liner from the plan; the proposed-fix block is a
# TODO marker the human fills in after looking at the actual rows.
BUCKET_BLURB: dict[str, str] = {
    "test-only": (
        "Test scaffolding noise — the compat-lane autotag patch mutates"
        " `entry.data` to add `__sandbox_group`, and some helper-integration"
        " tests or Syrupy snapshots assert the entry data is empty / matches"
        " a snapshot that pre-dates the tag. Not a v2 bridge bug."
    ),
    "proxy-missing": (
        "Phase 13 shipped proxies for all 32 entity domains. Any hit here"
        " means the integration registers an entity in a domain the bridge"
        " doesn't recognise — either a new domain landed in HA Core or the"
        " dispatch map missed one."
    ),
    "data-schema-stripped": (
        "Phase 14 added a `voluptuous_serialize`-based round-trip so flow"
        " schemas survive the bridge. Any hit here means a `vol.Schema`"
        " shape the serializer can't represent (custom validators, untagged"
        " `vol.Any`, etc.)."
    ),
    "service-schema-missing": (
        "Mirror of `data-schema-stripped` for `hass.services.async_register`."
        " Phase 14 ships the same bridge for service schemas; gaps here are"
        " edge cases (custom validators, schema-on-the-fly registrations)."
    ),
    "unique-id-not-propagated": (
        "Phase 14 marshals `flow.context['unique_id']` into the proxy. Hits"
        " here are flow shapes that set unique_id outside the standard"
        " `async_set_unique_id` path (e.g. discovery flows that abort"
        " inside `async_step_user`)."
    ),
    "restore-state-not-applied": (
        "Phase 9 warm-loads `RestoreStateData` from"
        " `<config>/.storage/sandbox/<group>/core.restore_state`. Hits"
        " here mean an integration's restore-state assertion fires before"
        " the warm-load completes, or expects state the previous run never"
        " persisted."
    ),
    "context-not-propagated": (
        "Phase 6 forwards events with the sandbox-side `context_id` but does"
        " NOT honour it for main's user/origin resolution. Integration tests"
        " that assert on `context.user_id` or `context.parent_id` fail here."
        " Carrying a richer Context shape is post-v2 work."
    ),
    "re-entrant-channel": (
        "Phase 12 made the channel dispatcher concurrent so a handler can"
        " issue `channel.call(...)`. Hits here mean a re-entrant shape we"
        " haven't seen — the semaphore cap might be too aggressive, or a"
        " handler chain exceeds the in-flight ceiling."
    ),
    "store-key-rejected": (
        "Phase 8's `RemoteStore` validator rejects keys containing `/`, `\\`,"
        " NUL, `.`, or `..`. An integration using one of those characters"
        " trips this. Probably wants a translation step on the sandbox side"
        " rather than relaxing the validator."
    ),
    "flow-step-not-async": (
        "Phase 4's flow proxy expects every step on the integration's"
        " `ConfigFlow` to be an async coroutine. A sync step would emit a"
        " `coroutine 'async_step_*' was never awaited` warning that this"
        " bucket catches."
    ),
    "integration-uses-deny-listed-platform": (
        "Classifier let an integration through that ships a"
        " `SANDBOX_INCOMPATIBLE_PLATFORMS` platform. Either the classifier"
        " has a bug or the platform-set should grow."
    ),
    "non-idempotent-service-handler": (
        "The `ai_task`/`image` shape Phase 1 surfaced — the service handler"
        " does material work before calling the entity method. Today's"
        " resolution is `ALWAYS_MAIN`; integrations that hit this should"
        " join that set or sandbox-handler interception needs designing"
        " (post-v2 work)."
    ),
    "dependencies-not-shared": (
        "Integration depends on a main-side service or piece of state that"
        " opt-in sharing doesn't expose. Tracked alongside the unfinished"
        " state-sharing consumer (see"
        " `sandbox/docs/design-share-states.md`)."
    ),
    "unknown": (
        "Catch-all bucket of last resort. Every entry here means the"
        " categorizer's regex set didn't fire — add a more-specific rule"
        " in `categorize_failures.py::RULES`."
    ),
}


def _bucket_priority(name: str) -> int:
    """Stable sort key — most-actionable buckets first when counts tie."""
    order = [
        "proxy-missing",
        "context-not-propagated",
        "data-schema-stripped",
        "service-schema-missing",
        "unique-id-not-propagated",
        "restore-state-not-applied",
        "re-entrant-channel",
        "non-idempotent-service-handler",
        "integration-uses-deny-listed-platform",
        "store-key-rejected",
        "flow-step-not-async",
        "dependencies-not-shared",
        "test-only",
        "unknown",
    ]
    try:
        return order.index(name)
    except ValueError:
        return len(order)


def render_backlog(payload: dict[str, dict[str, list[dict[str, str]]]]) -> str:
    """Render the BACKLOG.md draft."""
    lines: list[str] = [
        "# Sandbox — Phase 16 backlog",
        "",
        "**Auto-generated draft** from `BACKLOG_FAILURES.json`."
        " `generate_backlog.py` writes the skeleton; the *Proposed fix* and"
        " *Estimated size* lines need human curation before this lands as the"
        " final Phase 16 deliverable.",
        "",
        "Sections are ordered by integration count (largest first). Within"
        " each section the affected-integration roll-up is capped at 10 — the"
        " rest live in `BACKLOG_FAILURES.json` if a reviewer wants the full"
        " set.",
        "",
    ]

    bucket_rows = []
    for bucket, integrations in payload.items():
        if not integrations:
            continue
        failure_count = sum(len(nodes) for nodes in integrations.values())
        bucket_rows.append((bucket, failure_count, len(integrations)))

    bucket_rows.sort(key=lambda row: (-row[2], _bucket_priority(row[0]), row[0]))

    lines.append("## Bucket overview")
    lines.append("")
    lines.append("| Bucket | Failures | Integrations |")
    lines.append("| --- | ---: | ---: |")
    for bucket, failures, integrations_count in bucket_rows:
        lines.append(f"| `{bucket}` | {failures} | {integrations_count} |")
    lines.append("")

    for bucket, failures, integrations_count in bucket_rows:
        lines.append(f"## {bucket}")
        lines.append("")
        lines.append(BUCKET_BLURB.get(bucket, "_No description on file._"))
        lines.append("")
        lines.append(f"- **Failures:** {failures}")
        lines.append(f"- **Integrations affected:** {integrations_count}")
        lines.append("")
        integrations = payload[bucket]
        sorted_ints = sorted(
            integrations.items(), key=lambda pair: (-len(pair[1]), pair[0])
        )
        top = sorted_ints[:10]
        if top:
            lines.append("### Top integrations")
            lines.append("")
            lines.append("| Integration | Failure count |")
            lines.append("| --- | ---: |")
            for integration, nodes in top:
                lines.append(f"| `{integration}` | {len(nodes)} |")
            if len(sorted_ints) > 10:
                lines.append(
                    f"| _… +{len(sorted_ints) - 10} more in"
                    " `BACKLOG_FAILURES.json`_ |  |"
                )
            lines.append("")
            sample_int, sample_nodes = top[0]
            sample = sample_nodes[0]
            lines.append("### Representative failure")
            lines.append("")
            lines.append(f"`{sample_int}::{sample['node_id'].split('::')[-1]}`")
            lines.append("")
            lines.append("```")
            lines.append((sample["excerpt"] or "").strip())
            lines.append("```")
            lines.append("")
        lines.append("### Proposed fix")
        lines.append("")
        lines.append("_TODO: write before landing._")
        lines.append("")
        lines.append("### Estimated size")
        lines.append("")
        lines.append("_TODO: file/lines/complexity rough estimate._")
        lines.append("")

    lines.append("## `ALWAYS_MAIN` additions recommended")
    lines.append("")
    lines.append(
        "_TODO: list integrations whose dominant bucket is"
        " `non-idempotent-service-handler` or `dependencies-not-shared` and"
        " whose fix story is \"keep them on main\"._"
    )
    lines.append("")
    lines.append("## Classifier rule changes recommended")
    lines.append("")
    lines.append(
        "_TODO: list classifier deltas suggested by the sweep — e.g.,"
        " a new platform name to add to `SANDBOX_INCOMPATIBLE_PLATFORMS`,"
        " or an integration-type rule the classifier should tighten._"
    )
    lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_BACKLOG_JSON,
        help="Input JSON produced by `categorize_failures.py`.",
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_BACKLOG_MD,
        help="Where to write BACKLOG.md draft.",
    )
    args = parser.parse_args(argv)

    payload = json.loads(args.input.read_text())
    args.out.write_text(render_backlog(payload))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
