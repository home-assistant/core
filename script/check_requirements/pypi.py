"""PyPI metadata + PEP 740 provenance attestation lookups."""

from dataclasses import dataclass, field
import re
from typing import Any

from .fetch import get_json, is_known_host

# Characters that could escape markdown / HTML in the rendered comment or the
# prompt fence used to ship the artifact to the agent. PyPI maintainers are
# upstream-untrusted, so we strip these from any value we lift from PyPI
# metadata before it enters the artifact.
_UNSAFE = re.compile(r"[`\n\r<>]")


def _safe(text: str | None) -> str | None:
    """Strip characters that could escape markdown / HTML / a prompt fence."""
    if text is None:
        return None
    return _UNSAFE.sub("", text)


# Order matters — first hit wins.
_REPO_URL_KEYS = (
    "source",
    "source code",
    "repository",
    "code",
    "github",
    "gitlab",
    "codeberg",
    "homepage",
)

# Known CI publishers that appear in PEP 740 attestation bundles. Matched
# case-insensitively. Anything else is treated as inconclusive (NEEDS_AGENT).
_KNOWN_CI_PUBLISHERS = (
    "github",  # "GitHub" / "GitHub Actions"
    "gitlab",
    "google cloud",
    "activestate",
)

# `project_urls` keys that advertise where bugs are filed, lower-cased.
_TRACKER_URL_KEYS = frozenset(
    {"bug tracker", "bug reports", "issue tracker", "issues", "tracker"}
)


@dataclass(slots=True, frozen=True)
class Vulnerability:
    """One advisory entry for a specific package version (OSV / PyPA / GHSA)."""

    id: str
    aliases: tuple[str, ...]
    summary: str
    fixed_in: tuple[str, ...]
    link: str


@dataclass(slots=True)
class PypiPackageInfo:
    """The subset of PyPI metadata we care about for a specific version."""

    project_urls: dict[str, str]
    repo_url: str | None
    file_provenance_urls: list[str]  # may be empty
    found: bool  # False if the version doesn't exist on PyPI
    yanked: bool = False
    yanked_reason: str | None = None
    vulnerabilities: list[Vulnerability] = field(default_factory=list)


@dataclass(slots=True)
class ProvenanceResult:
    """Parsed PEP 740 attestation status."""

    has_attestation: bool
    publisher_kind: str | None
    recognized_publisher: bool
    detail: str


def _pick_repo_url(project_urls: dict[str, str]) -> str | None:
    """Pick the most likely source-repo URL from `info.project_urls`."""
    if not project_urls:
        return None
    lower_map = {k.lower(): v for k, v in project_urls.items()}
    for key in _REPO_URL_KEYS:
        url = lower_map.get(key)
        if url and is_known_host(url):
            return _safe(url)
    for url in project_urls.values():
        if is_known_host(url):
            return _safe(url)
    return None


def pick_tracker_url(project_urls: dict[str, str], repo_url: str) -> str | None:
    """Pick a tracker URL from `project_urls` that lives outside `repo_url`.

    A project may switch its repository's tracker off and point users at a
    tracker elsewhere; only such an off-repo URL is worth reporting.
    """
    repo = repo_url.rstrip("/").lower()
    for key, url in project_urls.items():
        if key.lower() not in _TRACKER_URL_KEYS:
            continue
        # Compare on a path boundary so a sibling repo is not read as our own.
        candidate = url.rstrip("/").lower()
        if candidate != repo and not candidate.startswith(f"{repo}/"):
            return _safe(url)
    return None


def fetch_package_info(name: str, version: str) -> PypiPackageInfo:
    """Fetch per-version PyPI metadata for one package."""
    versioned = get_json(f"https://pypi.org/pypi/{name}/{version}/json")
    if versioned is None:
        latest = get_json(f"https://pypi.org/pypi/{name}/json") or {}
        info = latest.get("info") or {}
        project_urls = info.get("project_urls") or {}
        return PypiPackageInfo(
            project_urls=project_urls,
            repo_url=_pick_repo_url(project_urls),
            file_provenance_urls=[],
            found=False,
        )

    info = versioned.get("info") or {}
    project_urls = info.get("project_urls") or {}
    # PyPI's `urls[].provenance` field is unreliable — it can be null even when
    # an attestation bundle exists at /integrity/.../provenance. Construct the
    # integrity URL ourselves from the filename; check_provenance probes it.
    # All files in a release share a publisher, so the first file is enough.
    provenance_urls: list[str] = []
    files = versioned.get("urls") or []
    for entry in files:
        filename = entry.get("filename")
        if filename:
            provenance_urls.append(
                f"https://pypi.org/integrity/{name}/{version}/{filename}/provenance"
            )
            break
    return PypiPackageInfo(
        project_urls=project_urls,
        repo_url=_pick_repo_url(project_urls),
        file_provenance_urls=provenance_urls,
        found=True,
        yanked=bool(info.get("yanked")),
        yanked_reason=_safe(info.get("yanked_reason")),
        vulnerabilities=_parse_vulnerabilities(versioned.get("vulnerabilities")),
    )


def _parse_vulnerabilities(raw: Any) -> list[Vulnerability]:
    """Extract non-withdrawn advisories from the PyPI `vulnerabilities` field."""
    if not isinstance(raw, list):
        return []
    out: list[Vulnerability] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if entry.get("withdrawn"):
            # Withdrawn means the advisory was removed by the maintainer
            # and should not be treated as valid.
            continue
        vid = _safe(entry.get("id"))
        if not vid:
            continue
        aliases_raw = entry.get("aliases") or []
        aliases = tuple(a for a in (_safe(str(x)) for x in aliases_raw if x) if a)
        fixed_raw = entry.get("fixed_in") or []
        fixed_in = tuple(f for f in (_safe(str(x)) for x in fixed_raw if x) if f)
        out.append(
            Vulnerability(
                id=vid,
                aliases=aliases,
                summary=_safe(entry.get("summary")) or "",
                fixed_in=fixed_in,
                link=_safe(entry.get("link")) or "",
            )
        )
    return out


def check_provenance(pkg: PypiPackageInfo) -> ProvenanceResult:
    """Resolve the provenance attestation, if any, to a Step 2b verdict."""
    if not pkg.found:
        return ProvenanceResult(
            has_attestation=False,
            publisher_kind=None,
            recognized_publisher=False,
            detail="Version not found on PyPI; cannot verify provenance.",
        )
    # Inspect any one file's attestation; all files of a release share a publisher.
    any_bundle_fetched = False
    for url in pkg.file_provenance_urls:
        bundle = get_json(url)
        if not bundle:
            continue
        any_bundle_fetched = True
        for entry in bundle.get("attestation_bundles") or []:
            publisher = entry.get("publisher") or {}
            kind = publisher.get("kind")
            if not kind:
                continue
            safe_kind = _safe(kind) or ""
            normalized_kind = safe_kind.strip().lower()
            recognized = normalized_kind in {
                token.strip().lower() for token in _KNOWN_CI_PUBLISHERS
            }
            return ProvenanceResult(
                has_attestation=True,
                publisher_kind=safe_kind,
                recognized_publisher=recognized,
                detail=(
                    f"Trusted Publisher attestation found ({safe_kind})."
                    if recognized
                    else (
                        f"Attestation present but publisher kind '{safe_kind}' is not in "
                        "the recognized-CI allowlist."
                    )
                ),
            )
    if any_bundle_fetched:
        return ProvenanceResult(
            has_attestation=False,
            publisher_kind=None,
            recognized_publisher=False,
            detail="Provenance URL was present but the attestation could not be parsed.",
        )
    return ProvenanceResult(
        has_attestation=False,
        publisher_kind=None,
        recognized_publisher=False,
        detail=(
            "No PEP 740 provenance attestation present on PyPI. Upload method "
            "cannot be verified from PyPI alone."
        ),
    )
