"""Orchestrate the deterministic requirements checks for one PR.

What the runner resolves itself (deterministic):
- `yanked`: PASS if the new release is live on PyPI, FAIL if it was yanked.
- `vulnerabilities`: FAIL if PyPI reports any non-withdrawn OSV / GHSA / CVE
  advisory for the new version; PASS otherwise.
- `ci_upload`: PASS / WARN / FAIL based on PEP 740 attestation on PyPI.
- `release_pipeline`: PASS only when the attestation already identifies a
  recognised CI publisher; otherwise NEEDS_AGENT.

What the runner defers to the LLM (NEEDS_AGENT):
- `repo_public`: reachability of the source-repo URL.
- `pr_link`: presence of the right link in the PR description.
- `release_pipeline`: inspection of the publish workflow when the attestation
  was missing or did not identify a recognised CI publisher.
- `async_blocking`: inspection of the dependency source for blocking I/O
  inside `async def` functions. Always deferred when the source repo is
  available — the deterministic stage cannot read the upstream source.
"""

from .diff import parse_diff
from .models import CheckKind, CheckResult, CheckRunResult, CheckStatus, PackageChange
from .pypi import PypiPackageInfo, check_provenance, fetch_package_info
from .render import render_comment


def _resolve_yanked(pkg: PackageChange, pypi_info: PypiPackageInfo) -> None:
    """Mark the release as yanked / not yanked."""
    if not pypi_info.found:
        pkg.checks[CheckKind.YANKED] = CheckResult(
            CheckStatus.FAIL,
            f"Version {pkg.new_version} not found on PyPI.",
        )
        return
    if pypi_info.yanked:
        reason = pypi_info.yanked_reason or "no reason provided by uploader"
        pkg.checks[CheckKind.YANKED] = CheckResult(
            CheckStatus.FAIL,
            f"Version {pkg.new_version} is yanked on PyPI ({reason}). "
            "Home Assistant should not depend on a yanked release.",
        )
        return
    pkg.checks[CheckKind.YANKED] = CheckResult(
        CheckStatus.PASS,
        f"Version {pkg.new_version} is a live (non-yanked) release.",
    )


def _resolve_vulnerabilities(pkg: PackageChange, pypi_info: PypiPackageInfo) -> None:
    """Flag versions with active OSV / GHSA / CVE advisories on PyPI."""
    if not pypi_info.found:
        pkg.checks[CheckKind.VULNERABILITIES] = CheckResult(
            CheckStatus.FAIL,
            f"Version {pkg.new_version} not found on PyPI.",
        )
        return
    vulns = pypi_info.vulnerabilities
    if not vulns:
        pkg.checks[CheckKind.VULNERABILITIES] = CheckResult(
            CheckStatus.PASS,
            f"No active advisories reported by PyPI for version {pkg.new_version}.",
        )
        return
    entries: list[str] = []
    for vuln in vulns:
        # Prefer a CVE alias as the primary label when present.
        cve = next((a for a in vuln.aliases if a.upper().startswith("CVE-")), None)
        label = cve or vuln.id
        fixed = ", ".join(vuln.fixed_in) if vuln.fixed_in else "no fix listed"
        if vuln.link:
            entries.append(f"[{label}]({vuln.link}) (fixed in: {fixed})")
        else:
            entries.append(f"{label} (fixed in: {fixed})")
    pkg.checks[CheckKind.VULNERABILITIES] = CheckResult(
        CheckStatus.FAIL,
        f"PyPI reports {len(vulns)} active advisories for version "
        f"{pkg.new_version}: " + "; ".join(entries) + ".",
    )


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
        _resolve_yanked(pkg, pypi_info)
        _resolve_vulnerabilities(pkg, pypi_info)
        _resolve_ci_upload_and_release_pipeline(pkg, pypi_info)
        if not pypi_info.found:
            fail = CheckResult(
                CheckStatus.FAIL,
                f"Version {pkg.new_version} not found on PyPI.",
            )
            pkg.checks[CheckKind.REPO_PUBLIC] = fail
            pkg.checks[CheckKind.PR_LINK] = fail
            pkg.checks[CheckKind.ASYNC_BLOCKING] = fail
        elif pkg.repo_url:
            pkg.checks[CheckKind.REPO_PUBLIC] = CheckResult(
                CheckStatus.NEEDS_AGENT,
                "Reachability of the source repository must be verified by the agent.",
            )
            pkg.checks[CheckKind.PR_LINK] = CheckResult(
                CheckStatus.NEEDS_AGENT,
                "Presence of the required link in the PR description must be verified by the agent.",
            )
            if pkg.old_version is None:
                async_reason = (
                    "New dependency: agent must review the entire source tree "
                    "at the new version for blocking I/O inside async functions."
                )
            else:
                async_reason = (
                    f"Version bump {pkg.old_version} → {pkg.new_version}: "
                    "agent must review only the diff for newly introduced "
                    "blocking I/O inside async functions."
                )
            pkg.checks[CheckKind.ASYNC_BLOCKING] = CheckResult(
                CheckStatus.NEEDS_AGENT, async_reason
            )
        else:
            fail = CheckResult(
                CheckStatus.FAIL,
                "PyPI does not advertise a source repository URL.",
            )
            pkg.checks[CheckKind.REPO_PUBLIC] = fail
            pkg.checks[CheckKind.PR_LINK] = fail
            pkg.checks[CheckKind.ASYNC_BLOCKING] = fail
    result = CheckRunResult(pr_number=pr_number, packages=packages)
    result.rendered_comment = render_comment(result)
    return result
