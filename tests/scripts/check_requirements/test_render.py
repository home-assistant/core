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
            CheckKind.SECURITY: _pass("baseline scan clean"),
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
            CheckKind.SECURITY: CheckResult(CheckStatus.NEEDS_AGENT, ""),
            CheckKind.PR_LINK: CheckResult(CheckStatus.NEEDS_AGENT, ""),
            CheckKind.ASYNC_BLOCKING: CheckResult(CheckStatus.NEEDS_AGENT, ""),
        },
    )
    rendered = render_comment(CheckRunResult(pr_number=1, packages=[pkg]))
    assert "{{CHECK_CELL:pkg:repo_public}}" in rendered
    assert "{{CHECK_DETAIL:pkg:repo_public}}" in rendered
    assert "{{CHECK_CELL:pkg:release_pipeline}}" in rendered
    assert "{{CHECK_DETAIL:pkg:release_pipeline}}" in rendered
    assert "{{CHECK_CELL:pkg:security}}" in rendered
    assert "{{CHECK_DETAIL:pkg:security}}" in rendered
    assert "{{CHECK_CELL:pkg:pr_link}}" in rendered
    assert "{{CHECK_CELL:pkg:async_blocking}}" in rendered
    assert "{{CHECK_DETAIL:pkg:async_blocking}}" in rendered
    assert "<details open>" in rendered
    # A deterministic WARN (CI_UPLOAD) already forces the attention verdict
    # regardless of how the agent resolves the pending checks, so the summary
    # is rendered directly rather than deferred to the agent.
    assert "⚠️ Some checks require attention — see the details below." in rendered
    assert "{{SUMMARY}}" not in rendered


def test_render_pass_or_pending_defers_summary_to_agent() -> None:
    """With only PASS and NEEDS_AGENT checks, the summary is left as a placeholder.

    The final verdict depends entirely on how the agent resolves the pending
    checks, so the deterministic stage must not bake in a summary line.
    """
    pkg = PackageChange(
        name="pkg",
        old_version=None,
        new_version="1.0.0",
        repo_url="https://github.com/x/pkg",
        checks={
            CheckKind.CI_UPLOAD: _pass("attestation found"),
            CheckKind.SECURITY: CheckResult(CheckStatus.NEEDS_AGENT, ""),
            CheckKind.ASYNC_BLOCKING: CheckResult(CheckStatus.NEEDS_AGENT, ""),
        },
    )
    rendered = render_comment(CheckRunResult(pr_number=1, packages=[pkg]))
    assert "{{SUMMARY}}" in rendered
    assert "All requirements checks passed. ✅" not in rendered
    assert "⚠️ Some checks require attention" not in rendered


def test_render_deterministic_warn_renders_attention_summary() -> None:
    """A WARN with no agent-pending checks renders the attention line directly."""
    pkg = PackageChange(
        name="pkg",
        old_version="1.0.0",
        new_version="1.1.0",
        repo_url="https://github.com/x/pkg",
        checks={
            CheckKind.CI_UPLOAD: _pass("attestation found"),
            CheckKind.SECURITY: CheckResult(CheckStatus.WARN, "partial scan"),
        },
    )
    rendered = render_comment(CheckRunResult(pr_number=1, packages=[pkg]))
    assert "⚠️ Some checks require attention — see the details below." in rendered
    assert "{{SUMMARY}}" not in rendered


def test_render_empty_change_set() -> None:
    """A run with no package changes renders an explicit empty-state message."""
    rendered = render_comment(CheckRunResult(pr_number=1))
    assert "No tracked requirement changes detected" in rendered


def test_render_embeds_head_sha_as_commit_link() -> None:
    """A head SHA renders a commit link whose URL carries the full SHA."""
    pkg = PackageChange(
        name="pkg",
        old_version="1.0.0",
        new_version="1.1.0",
        repo_url="https://github.com/x/pkg",
        checks={CheckKind.CI_UPLOAD: _pass("ok")},
    )
    sha = "abc1234def5678abc1234def5678abc1234def56"
    rendered = render_comment(CheckRunResult(pr_number=1, head_sha=sha, packages=[pkg]))
    # Short SHA shown to humans, full SHA recoverable from the link URL.
    assert (
        f"Checked at commit [`abc1234`]"
        f"(https://github.com/home-assistant/core/commit/{sha})."
    ) in rendered
    assert rendered.startswith("<!-- requirements-check -->\n")


def test_render_without_head_sha_omits_commit_line() -> None:
    """With no head SHA, the commit line is absent entirely."""
    rendered = render_comment(CheckRunResult(pr_number=1))
    assert "Checked at commit" not in rendered


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
