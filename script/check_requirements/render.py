"""Render the final PR comment from check results.

The comment is rendered fully up-front. Checks whose status is `NEEDS_AGENT`
get `{{CHECK_CELL:<package>:<kind>}}` and `{{CHECK_DETAIL:<package>:<kind>}}`
placeholders that the agent replaces before posting.

To add a new check kind: extend `CheckKind` and add an entry to `_CHECK_DISPLAY`
below. The agent prompt must also gain a matching instruction section, or the
agent will refuse to resolve the new kind.
"""

from .models import CheckKind, CheckRunResult, CheckStatus, PackageChange

MARKER = "<!-- requirements-check -->"
HEADER = "## Check requirements"

# Column / bullet labels per check kind, in display order.
_CHECK_DISPLAY: tuple[tuple[CheckKind, str], ...] = (
    (CheckKind.VULNERABILITIES, "No Advisories"),
    (CheckKind.YANKED, "Not Yanked"),
    (CheckKind.REPO_PUBLIC, "Repo Public"),
    (CheckKind.CI_UPLOAD, "CI Upload"),
    (CheckKind.RELEASE_PIPELINE, "Release Pipeline"),
    (CheckKind.PR_LINK, "PR Link"),
    (CheckKind.ASYNC_BLOCKING, "Async Safe"),
)

_ICONS: dict[CheckStatus, str] = {
    CheckStatus.PASS: "✅",
    CheckStatus.WARN: "⚠️",
    CheckStatus.FAIL: "❌",
}
SKIPPED = "—"


def _placeholder(slot: str, pkg: PackageChange, kind: CheckKind) -> str:
    """Placeholder marker the agent replaces before posting."""
    return f"{{{{{slot}:{pkg.name}:{kind.value}}}}}"


def _old_cell(pkg: PackageChange) -> str:
    return pkg.old_version or SKIPPED


def _overall_status(pkg: PackageChange) -> CheckStatus | None:
    """Aggregate the per-package status across all checks."""
    statuses = [c.status for c in pkg.checks.values()]
    if CheckStatus.FAIL in statuses:
        return CheckStatus.FAIL
    if CheckStatus.WARN in statuses:
        return CheckStatus.WARN
    if CheckStatus.NEEDS_AGENT in statuses:
        return None
    return CheckStatus.PASS


def _summary_line(packages: list[PackageChange]) -> str:
    if all(_overall_status(p) == CheckStatus.PASS for p in packages):
        return "All requirements checks passed. ✅"
    return "⚠️ Some checks require attention — see the details below."


def _cell(pkg: PackageChange, kind: CheckKind) -> str:
    result = pkg.checks.get(kind)
    if result is None:
        return SKIPPED
    if result.status == CheckStatus.NEEDS_AGENT:
        return _placeholder("CHECK_CELL", pkg, kind)
    return _ICONS.get(result.status, SKIPPED)


def _table(packages: list[PackageChange]) -> str:
    labels = [label for _, label in _CHECK_DISPLAY]
    rows = [
        "| Package | Old | New | " + " | ".join(labels) + " |",
        "|" + "|".join("---" for _ in range(3 + len(labels))) + "|",
    ]
    for pkg in packages:
        cells = [_cell(pkg, kind) for kind, _ in _CHECK_DISPLAY]
        rows.append(
            "| "
            + " | ".join([pkg.name, _old_cell(pkg), pkg.new_version, *cells])
            + " |"
        )
    return "\n".join(rows)


def _bullet(pkg: PackageChange, kind: CheckKind, label: str) -> str:
    result = pkg.checks.get(kind)
    if result is None:
        return f"- **{label}**: {SKIPPED} skipped."
    if result.status == CheckStatus.NEEDS_AGENT:
        return f"- **{label}**: {_placeholder('CHECK_DETAIL', pkg, kind)}"
    return f"- **{label}**: {_ICONS[result.status]} {result.details}"


def _details_block(pkg: PackageChange) -> str:
    overall = _overall_status(pkg)
    is_open = overall != CheckStatus.PASS
    version = (
        f"{pkg.old_version} → {pkg.new_version}" if pkg.old_version else pkg.new_version
    )
    summary = f"<summary><strong>📦 {pkg.name}: {version}</strong></summary>"
    open_attr = " open" if is_open else ""
    body_lines = [_bullet(pkg, kind, label) for kind, label in _CHECK_DISPLAY]
    return (
        f"<details{open_attr}>\n{summary}\n\n"
        + "\n".join(body_lines)
        + "\n\n</details>"
    )


def render_comment(result: CheckRunResult) -> str:
    """Build the full markdown comment, including placeholder markers."""
    if not result.packages:
        return f"{MARKER}\n{HEADER}\n\nNo tracked requirement changes detected. ✅"
    return "\n\n".join(
        [
            f"{MARKER}\n{HEADER}\n\n{_summary_line(result.packages)}",
            _table(result.packages),
            *[_details_block(p) for p in result.packages],
        ]
    )
