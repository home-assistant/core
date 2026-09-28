"""Issue-tracker lookups on the source-code hosts PyPI metadata can point at.

PyPI only advertises where a project's source lives; whether users can report
bugs there is a per-host repository flag. An unsupported host, or an API that
does not answer, resolves to "unknown" rather than to a verdict.
"""

from collections.abc import Mapping
import os
from typing import Any
from urllib.parse import urlparse

from .fetch import HEADERS, get_json, host_of, post_json

_GITLAB_GRAPHQL_URL = "https://gitlab.com/api/graphql"
_GITLAB_QUERY = "query($path: ID!) { project(fullPath: $path) { issuesEnabled } }"
# How far to walk up a GitLab path before giving up; the URL is upstream
# PyPI metadata, so its depth is not ours to trust.
_GITLAB_MAX_FALLBACKS = 3


def _github_headers() -> Mapping[str, str]:
    """Headers for api.github.com; the token lifts the anonymous rate limit."""
    if token := os.environ.get("GITHUB_TOKEN"):
        return {**HEADERS, "Authorization": f"Bearer {token}"}
    return HEADERS


def _path_segments(url: str) -> list[str]:
    return [segment for segment in urlparse(url).path.split("/") if segment]


def _owner_repo(url: str) -> tuple[str, str] | None:
    """Split the first two path segments into `(owner, repo)`."""
    segments = _path_segments(url)
    if len(segments) < 2:
        return None
    return segments[0], segments[1].removesuffix(".git")


def _gitlab_paths(url: str) -> list[str]:
    """Candidate GitLab project paths for `url`, longest first.

    A project path may contain subgroups, so `a/b/c` is either the project
    `a/b/c` or the project `a/b` followed by a legacy (pre-`/-/`) route such as
    `/issues`. Only GitLab can tell the two apart, so try the full path and
    then walk up from it, bounded by `_GITLAB_MAX_FALLBACKS`.
    """
    segments = _path_segments(url)
    if "-" in segments:  # `/-/` separates the project path from the GitLab route
        segments = segments[: segments.index("-")]
    shortest = max(2, len(segments) - _GITLAB_MAX_FALLBACKS)
    paths: list[str] = []
    for depth in range(len(segments), shortest - 1, -1):
        *groups, project = segments[:depth]
        if project := project.removesuffix(".git"):
            paths.append("/".join([*groups, project]))
    return paths


def _bool_field(data: dict[str, Any], key: str) -> bool | None:
    value = data.get(key)
    return value if isinstance(value, bool) else None


def _forge_issues_enabled(api_url: str, headers: Mapping[str, str]) -> bool | None:
    """GitHub and Forgejo (Codeberg) both expose the tracker as `has_issues`."""
    data = get_json(api_url, headers)
    return _bool_field(data, "has_issues") if data else None


def _gitlab_issues_enabled(repo_url: str) -> bool | None:
    """GitLab exposes the flag over GraphQL only.

    Its anonymous REST project payload carries neither `issues_access_level`
    nor `issues_enabled`, and the REST issue list answers `200 []` even for a
    project whose tracker is off.
    """
    for path in _gitlab_paths(repo_url):
        body = post_json(
            _GITLAB_GRAPHQL_URL, {"query": _GITLAB_QUERY, "variables": {"path": path}}
        )
        if body is None:
            return None
        project = (body.get("data") or {}).get("project")
        if isinstance(project, dict):
            return _bool_field(project, "issuesEnabled")
    return None


def fetch_issues_enabled(repo_url: str) -> bool | None:
    """Return whether `repo_url` accepts issue reports.

    None when the host is not supported or its API did not answer.
    """
    host = host_of(repo_url)
    if host == "gitlab.com":
        return _gitlab_issues_enabled(repo_url)
    if (owner_repo := _owner_repo(repo_url)) is None:
        return None
    owner, repo = owner_repo
    if host == "github.com":
        return _forge_issues_enabled(
            f"https://api.github.com/repos/{owner}/{repo}", _github_headers()
        )
    if host == "codeberg.org":
        return _forge_issues_enabled(
            f"https://codeberg.org/api/v1/repos/{owner}/{repo}", HEADERS
        )
    return None
