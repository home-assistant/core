"""Tests for script.check_requirements.runner."""

import json

import pytest

from script.check_requirements.models import CheckKind, CheckStatus
from script.check_requirements.pypi import ProvenanceResult, PypiPackageInfo
from script.check_requirements.runner import run_checks


def _patch_pypi(
    monkeypatch: pytest.MonkeyPatch,
    pypi_info: PypiPackageInfo,
    prov: ProvenanceResult,
) -> None:
    monkeypatch.setattr(
        "script.check_requirements.runner.fetch_package_info",
        lambda name, version: pypi_info,
    )
    monkeypatch.setattr(
        "script.check_requirements.runner.check_provenance", lambda info: prov
    )


def test_runner_attestation_recognised(monkeypatch: pytest.MonkeyPatch) -> None:
    """Recognised attestation → ci_upload PASS, release_pipeline PASS, repo + pr_link needs_agent."""
    _patch_pypi(
        monkeypatch,
        PypiPackageInfo(
            project_urls={"Source": "https://github.com/example/pkg"},
            repo_url="https://github.com/example/pkg",
            file_provenance_urls=["whatever"],
            found=True,
        ),
        ProvenanceResult(
            has_attestation=True,
            publisher_kind="GitHub",
            recognized_publisher=True,
            detail="Trusted Publisher attestation found (GitHub).",
        ),
    )
    diff = (
        "diff --git a/requirements_all.txt b/requirements_all.txt\n"
        "--- a/requirements_all.txt\n"
        "+++ b/requirements_all.txt\n"
        "@@ -1 +1 @@\n"
        "-pkg==1.0.0\n"
        "+pkg==1.1.0\n"
    )
    result = run_checks(pr_number=42, diff_text=diff)
    assert len(result.packages) == 1
    pkg = result.packages[0]
    assert pkg.checks[CheckKind.CI_UPLOAD].status == CheckStatus.PASS
    assert pkg.checks[CheckKind.RELEASE_PIPELINE].status == CheckStatus.PASS
    assert pkg.checks[CheckKind.REPO_PUBLIC].status == CheckStatus.NEEDS_AGENT
    assert pkg.checks[CheckKind.PR_LINK].status == CheckStatus.NEEDS_AGENT
    assert pkg.checks[CheckKind.SECURITY].status == CheckStatus.NEEDS_AGENT
    assert result.needs_agent is True


def test_runner_no_attestation(monkeypatch: pytest.MonkeyPatch) -> None:
    """No attestation → ci_upload WARN, release_pipeline NEEDS_AGENT."""
    _patch_pypi(
        monkeypatch,
        PypiPackageInfo(
            project_urls={"Source": "https://github.com/example/pkg"},
            repo_url="https://github.com/example/pkg",
            file_provenance_urls=[],
            found=True,
        ),
        ProvenanceResult(
            has_attestation=False,
            publisher_kind=None,
            recognized_publisher=False,
            detail="No PEP 740 provenance attestation present on PyPI.",
        ),
    )
    diff = (
        "diff --git a/requirements_all.txt b/requirements_all.txt\n"
        "--- a/requirements_all.txt\n"
        "+++ b/requirements_all.txt\n"
        "@@ -1 +1 @@\n"
        "-pkg==1.0.0\n"
        "+pkg==1.1.0\n"
    )
    result = run_checks(pr_number=1, diff_text=diff)
    pkg = result.packages[0]
    assert pkg.checks[CheckKind.CI_UPLOAD].status == CheckStatus.WARN
    assert pkg.checks[CheckKind.RELEASE_PIPELINE].status == CheckStatus.NEEDS_AGENT


def test_runner_attestation_present_but_publisher_unrecognised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Attestation present but publisher unknown → ci_upload WARN, release_pipeline NEEDS_AGENT."""
    _patch_pypi(
        monkeypatch,
        PypiPackageInfo(
            project_urls={"Source": "https://github.com/example/pkg"},
            repo_url="https://github.com/example/pkg",
            file_provenance_urls=["whatever"],
            found=True,
        ),
        ProvenanceResult(
            has_attestation=True,
            publisher_kind="AcmeCI",
            recognized_publisher=False,
            detail="Attestation present but publisher kind 'AcmeCI' is not recognised.",
        ),
    )
    diff = (
        "diff --git a/requirements_all.txt b/requirements_all.txt\n"
        "--- a/requirements_all.txt\n"
        "+++ b/requirements_all.txt\n"
        "@@ -1 +1 @@\n"
        "-pkg==1.0.0\n"
        "+pkg==1.1.0\n"
    )
    result = run_checks(pr_number=1, diff_text=diff)
    pkg = result.packages[0]
    assert pkg.checks[CheckKind.CI_UPLOAD].status == CheckStatus.WARN
    assert pkg.checks[CheckKind.RELEASE_PIPELINE].status == CheckStatus.NEEDS_AGENT
    assert "publisher unrecognised" in pkg.checks[CheckKind.RELEASE_PIPELINE].details


def test_runner_marks_missing_version_as_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A version that doesn't exist on PyPI must FAIL, not request the agent."""
    _patch_pypi(
        monkeypatch,
        PypiPackageInfo(
            project_urls={},
            repo_url=None,
            file_provenance_urls=[],
            found=False,
        ),
        ProvenanceResult(
            has_attestation=False,
            publisher_kind=None,
            recognized_publisher=False,
            detail="Version not found on PyPI.",
        ),
    )
    diff = (
        "diff --git a/requirements_all.txt b/requirements_all.txt\n"
        "--- a/requirements_all.txt\n"
        "+++ b/requirements_all.txt\n"
        "@@ -1 +1 @@\n"
        "-pkg==1.0.0\n"
        "+pkg==9.9.9\n"
    )
    result = run_checks(pr_number=1, diff_text=diff)
    pkg = result.packages[0]
    assert pkg.checks[CheckKind.CI_UPLOAD].status == CheckStatus.FAIL
    assert pkg.checks[CheckKind.RELEASE_PIPELINE].status == CheckStatus.FAIL
    # No repo URL → short-circuit to FAIL
    assert pkg.checks[CheckKind.REPO_PUBLIC].status == CheckStatus.FAIL
    assert pkg.checks[CheckKind.PR_LINK].status == CheckStatus.FAIL
    assert pkg.checks[CheckKind.SECURITY].status == CheckStatus.FAIL
    assert result.needs_agent is False


def test_runner_pypi_found_but_no_repo_url_fails_repo_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A package on PyPI without a source URL fails repo_public and pr_link."""
    _patch_pypi(
        monkeypatch,
        PypiPackageInfo(
            project_urls={},
            repo_url=None,
            file_provenance_urls=[],
            found=True,
        ),
        ProvenanceResult(
            has_attestation=False,
            publisher_kind=None,
            recognized_publisher=False,
            detail="No PEP 740 provenance attestation present on PyPI.",
        ),
    )
    diff = (
        "diff --git a/requirements_all.txt b/requirements_all.txt\n"
        "--- a/requirements_all.txt\n"
        "+++ b/requirements_all.txt\n"
        "@@ -1 +1 @@\n"
        "-pkg==1.0.0\n"
        "+pkg==1.1.0\n"
    )
    result = run_checks(pr_number=1, diff_text=diff)
    pkg = result.packages[0]
    assert pkg.checks[CheckKind.REPO_PUBLIC].status == CheckStatus.FAIL
    assert pkg.checks[CheckKind.PR_LINK].status == CheckStatus.FAIL
    assert pkg.checks[CheckKind.SECURITY].status == CheckStatus.FAIL
    assert "does not advertise" in pkg.checks[CheckKind.REPO_PUBLIC].details
    assert "cannot be inspected" in pkg.checks[CheckKind.SECURITY].details


def test_runner_serialises_to_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """The artifact contract: `to_dict()` is JSON-serialisable with expected keys."""
    _patch_pypi(
        monkeypatch,
        PypiPackageInfo(
            project_urls={"Source": "https://github.com/x/y"},
            repo_url="https://github.com/x/y",
            file_provenance_urls=["whatever"],
            found=True,
        ),
        ProvenanceResult(
            has_attestation=True,
            publisher_kind="GitHub",
            recognized_publisher=True,
            detail="ok",
        ),
    )
    diff = (
        "diff --git a/requirements_all.txt b/requirements_all.txt\n"
        "--- a/requirements_all.txt\n"
        "+++ b/requirements_all.txt\n"
        "@@ -1 +1 @@\n"
        "-pkg==1.0.0\n"
        "+pkg==1.1.0\n"
    )
    result = run_checks(pr_number=42, diff_text=diff)
    serialised = json.dumps(result.to_dict())
    assert '"rendered_comment"' in serialised
    assert '"needs_agent"' in serialised
    assert '"checks"' in serialised
    assert '"repo_public"' in serialised  # check kinds are in the JSON
