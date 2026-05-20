"""Orchestrate the deterministic requirements checks for one PR.

What the runner resolves itself (deterministic):
- `ci_upload`: PASS / WARN / FAIL based on PEP 740 attestation on PyPI.
- `release_pipeline`: PASS only when the attestation already identifies a
  recognised CI publisher; otherwise NEEDS_AGENT.

What the runner defers to the LLM (NEEDS_AGENT):
- `repo_public`: reachability of the source-repo URL.
- `pr_link`: presence of the right link in the PR description.
- `release_pipeline`: inspection of the publish workflow when the attestation
  was missing or did not identify a recognised CI publisher.
"""

from .diff import parse_diff
from .models import CheckKind, CheckResult, CheckRunResult, CheckStatus, PackageChange
from .pypi import PypiPackageInfo, check_provenance, fetch_package_info
from .render import render_comment


def _resolve_ci_upload_and_release_pipeline(
    pkg: PackageChange, pypi_info: PypiPackageInfo
) -> None:
    """Set ci_upload and release_pipeline from the PEP 740 attestation."""
    if not pypi_info.found:
        pkg.checks[CheckKind.CI_UPLOAD] = CheckResult(
            CheckStatus.FAIL,
            f"Version {pkg.new_version} not found on PyPI.",
        )
        pkg.checks[CheckKind.RELEASE_PIPELINE] = CheckResult(
            CheckStatus.FAIL,
            "Cannot inspect release pipeline for a version that doesn't exist.",
        )
        return
    prov = check_provenance(pypi_info)
    pkg.publisher_kind = prov.publisher_kind
    if prov.has_attestation and prov.recognized_publisher:
        pkg.checks[CheckKind.CI_UPLOAD] = CheckResult(CheckStatus.PASS, prov.detail)
        pkg.checks[CheckKind.RELEASE_PIPELINE] = CheckResult(
            CheckStatus.PASS,
            f"OIDC via Trusted Publisher attestation ({prov.publisher_kind}); "
            "automated CI upload verified by PyPI.",
        )
        return
    pkg.checks[CheckKind.CI_UPLOAD] = CheckResult(CheckStatus.WARN, prov.detail)
    if prov.has_attestation:
        rp_reason = (
            "Attestation present but publisher unrecognised; release pipeline "
            "needs LLM inspection."
        )
    else:
        rp_reason = (
            "No provenance attestation on PyPI; release pipeline needs LLM inspection."
        )
    pkg.checks[CheckKind.RELEASE_PIPELINE] = CheckResult(
        CheckStatus.NEEDS_AGENT, rp_reason
    )


def run_checks(
    pr_number: int,
    diff_text: str,
) -> CheckRunResult:
    """Run every deterministic check and return the aggregated result."""
    packages = parse_diff(diff_text)
    for pkg in packages:
        pypi_info = fetch_package_info(pkg.name, pkg.new_version)
        pkg.repo_url = pypi_info.repo_url
        _resolve_ci_upload_and_release_pipeline(pkg, pypi_info)
        if not pypi_info.found:
            fail = CheckResult(
                CheckStatus.FAIL,
                f"Version {pkg.new_version} not found on PyPI.",
            )
            pkg.checks[CheckKind.REPO_PUBLIC] = fail
            pkg.checks[CheckKind.PR_LINK] = fail
        elif pkg.repo_url:
            pkg.checks[CheckKind.REPO_PUBLIC] = CheckResult(
                CheckStatus.NEEDS_AGENT,
                "Reachability of the source repository must be verified by the agent.",
            )
            pkg.checks[CheckKind.PR_LINK] = CheckResult(
                CheckStatus.NEEDS_AGENT,
                "Presence of the required link in the PR description must be verified by the agent.",
            )
        else:
            fail = CheckResult(
                CheckStatus.FAIL,
                "PyPI does not advertise a source repository URL.",
            )
            pkg.checks[CheckKind.REPO_PUBLIC] = fail
            pkg.checks[CheckKind.PR_LINK] = fail
    result = CheckRunResult(pr_number=pr_number, packages=packages)
    result.rendered_comment = render_comment(result)
    return result
