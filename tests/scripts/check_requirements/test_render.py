"""Tests for script.check_requirements.render."""

from script.check_requirements.models import (
    CheckKind,
    CheckResult,
    CheckRunResult,
    CheckStatus,
    PackageChange,
)
from script.check_requirements.render import render_comment


def _pass(detail: str) -> CheckResult:
    return CheckResult(CheckStatus.PASS, detail)


def test_render_all_conclusive_collapses_details() -> None:
    """When every check passes, the rendered details section is collapsed."""
    pkg = PackageChange(
        name="pkg",
        old_version="1.0.0",
        new_version="1.1.0",
        repo_url="https://github.com/x/pkg",
        checks={
            CheckKind.REPO_PUBLIC: _pass("public"),
            CheckKind.CI_UPLOAD: _pass("attestation found"),
            CheckKind.RELEASE_PIPELINE: _pass("OIDC via attestation"),
            CheckKind.PR_LINK: _pass("link found"),
            CheckKind.ASYNC_BLOCKING: _pass("no blocking calls in async"),
        },
    )
    result = CheckRunResult(pr_number=1, packages=[pkg])
    rendered = render_comment(result)
    assert rendered.startswith("<!-- requirements-check -->")
    assert "All requirements checks passed. ✅" in rendered
    assert "<details>" in rendered and "<details open>" not in rendered
    assert "{{CHECK_CELL" not in rendered
    assert "{{CHECK_DETAIL" not in rendered


def test_render_needs_agent_emits_generic_placeholders() -> None:
    """Each NEEDS_AGENT check produces cell and detail placeholders for the agent."""
    pkg = PackageChange(
        name="pkg",
        old_version=None,
        new_version="1.0.0",
        repo_url="https://github.com/x/pkg",
        checks={
            CheckKind.REPO_PUBLIC: CheckResult(CheckStatus.NEEDS_AGENT, ""),
            CheckKind.CI_UPLOAD: CheckResult(CheckStatus.WARN, "no attestation"),
            CheckKind.RELEASE_PIPELINE: CheckResult(CheckStatus.NEEDS_AGENT, ""),
            CheckKind.PR_LINK: CheckResult(CheckStatus.NEEDS_AGENT, ""),
            CheckKind.ASYNC_BLOCKING: CheckResult(CheckStatus.NEEDS_AGENT, ""),
        },
    )
    rendered = render_comment(CheckRunResult(pr_number=1, packages=[pkg]))
    assert "{{CHECK_CELL:pkg:repo_public}}" in rendered
    assert "{{CHECK_DETAIL:pkg:repo_public}}" in rendered
    assert "{{CHECK_CELL:pkg:release_pipeline}}" in rendered
    assert "{{CHECK_DETAIL:pkg:release_pipeline}}" in rendered
    assert "{{CHECK_CELL:pkg:pr_link}}" in rendered
    assert "{{CHECK_CELL:pkg:async_blocking}}" in rendered
    assert "{{CHECK_DETAIL:pkg:async_blocking}}" in rendered
    assert "<details open>" in rendered


def test_render_empty_change_set() -> None:
    """A run with no package changes renders an explicit empty-state message."""
    rendered = render_comment(CheckRunResult(pr_number=1))
    assert "No tracked requirement changes detected" in rendered


def test_render_missing_check_renders_as_skipped() -> None:
    """A check kind absent from `pkg.checks` shows the skipped marker in both cells and bullets."""
    pkg = PackageChange(
        name="pkg",
        old_version="1.0.0",
        new_version="1.1.0",
        repo_url="https://github.com/x/pkg",
        checks={
            CheckKind.CI_UPLOAD: CheckResult(CheckStatus.PASS, "ok"),
            # REPO_PUBLIC, RELEASE_PIPELINE, PR_LINK intentionally omitted
        },
    )
    rendered = render_comment(CheckRunResult(pr_number=1, packages=[pkg]))
    assert "— skipped." in rendered
    # The skipped marker should appear in the table cells for missing kinds.
    assert " — |" in rendered or "| — " in rendered
