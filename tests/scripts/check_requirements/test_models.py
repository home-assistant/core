"""Tests for script.check_requirements.models."""

import pytest

from script.check_requirements.models import (
    CheckKind,
    CheckResult,
    CheckRunResult,
    CheckStatus,
    PackageChange,
)


def _pkg(checks: dict[CheckKind, CheckResult]) -> PackageChange:
    return PackageChange(
        name="pkg",
        old_version=None,
        new_version="1.0.0",
        checks=checks,
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        pytest.param(CheckStatus.PASS, False, id="pass"),
        pytest.param(CheckStatus.WARN, False, id="warn"),
        pytest.param(CheckStatus.FAIL, False, id="fail"),
        pytest.param(CheckStatus.NEEDS_AGENT, True, id="needs-agent"),
    ],
)
def test_package_needs_agent(status: CheckStatus, expected: bool) -> None:
    """Only NEEDS_AGENT statuses cause a package to flag for agent review."""
    pkg = _pkg({CheckKind.RELEASE_PIPELINE: CheckResult(status, "")})
    assert pkg.needs_agent is expected


def test_package_needs_agent_only_when_some_check_is_needs_agent() -> None:
    """A package without any NEEDS_AGENT check does not need agent review."""
    pkg = _pkg(
        {
            CheckKind.CI_UPLOAD: CheckResult(CheckStatus.PASS, ""),
            CheckKind.RELEASE_PIPELINE: CheckResult(CheckStatus.FAIL, ""),
        }
    )
    assert pkg.needs_agent is False


def test_run_result_needs_agent_aggregates() -> None:
    """CheckRunResult.needs_agent is True if any contained package needs agent."""
    p1 = _pkg({CheckKind.CI_UPLOAD: CheckResult(CheckStatus.PASS, "")})
    p2 = _pkg({CheckKind.RELEASE_PIPELINE: CheckResult(CheckStatus.NEEDS_AGENT, "")})
    p2.name = "p2"
    run = CheckRunResult(pr_number=1, packages=[p1, p2])
    assert run.needs_agent is True
