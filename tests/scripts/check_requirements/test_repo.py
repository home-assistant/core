"""Tests for script.check_requirements.repo."""

from typing import Any

import pytest
import requests
import requests_mock as rm

from script.check_requirements.repo import fetch_issues_enabled

_GITHUB_URL = "https://github.com/example/pkg"
_CODEBERG_URL = "https://codeberg.org/example/pkg"
_GITLAB_URL = "https://gitlab.com/example/pkg"
_GRAPHQL_URL = "https://gitlab.com/api/graphql"


def _graphql(enabled: bool | None) -> dict[str, Any]:
    return {"data": {"project": {"issuesEnabled": enabled}}}


@pytest.mark.parametrize(
    ("repo_url", "api_url"),
    [
        pytest.param(
            _GITHUB_URL, "https://api.github.com/repos/example/pkg", id="github"
        ),
        pytest.param(
            "https://www.github.com/example/pkg.git",
            "https://api.github.com/repos/example/pkg",
            id="github-www-and-git-suffix",
        ),
        pytest.param(
            "https://github.com/example/pkg/issues",
            "https://api.github.com/repos/example/pkg",
            id="github-sub-path",
        ),
        pytest.param(
            _CODEBERG_URL,
            "https://codeberg.org/api/v1/repos/example/pkg",
            id="codeberg",
        ),
    ],
)
def test_fetch_issues_enabled_queries_the_forge_api(
    requests_mock: rm.Mocker, repo_url: str, api_url: str
) -> None:
    """GitHub and Codeberg each resolve to their own repository endpoint."""
    requests_mock.get(rm.ANY, json={"has_issues": True})
    assert fetch_issues_enabled(repo_url) is True
    assert requests_mock.last_request.url == api_url


@pytest.mark.parametrize(
    ("repo_url", "expected_path"),
    [
        pytest.param(_GITLAB_URL, "example/pkg", id="gitlab"),
        pytest.param(
            "https://gitlab.com/example/pkg.git", "example/pkg", id="git-suffix"
        ),
        pytest.param(
            "https://gitlab.com/group/subgroup/pkg/-/tree/main",
            "group/subgroup/pkg",
            id="subgroup-and-route",
        ),
    ],
)
def test_fetch_issues_enabled_queries_gitlab_graphql(
    requests_mock: rm.Mocker, repo_url: str, expected_path: str
) -> None:
    """GitLab is asked over GraphQL, with the project path passed as a variable."""
    requests_mock.post(rm.ANY, json=_graphql(True))
    assert fetch_issues_enabled(repo_url) is True
    assert requests_mock.last_request.url == _GRAPHQL_URL
    assert requests_mock.last_request.json()["variables"] == {"path": expected_path}


@pytest.mark.parametrize(
    ("repo_url", "payload", "expected"),
    [
        pytest.param(_GITHUB_URL, {"has_issues": True}, True, id="github-enabled"),
        pytest.param(_GITHUB_URL, {"has_issues": False}, False, id="github-disabled"),
        pytest.param(_GITHUB_URL, {}, None, id="github-field-absent"),
        pytest.param(_CODEBERG_URL, {"has_issues": True}, True, id="codeberg-enabled"),
        pytest.param(
            _CODEBERG_URL, {"has_issues": False}, False, id="codeberg-disabled"
        ),
    ],
)
def test_fetch_issues_enabled_reads_the_forge_flag(
    requests_mock: rm.Mocker,
    repo_url: str,
    payload: dict[str, Any],
    expected: bool | None,
) -> None:
    """The `has_issues` flag maps onto the tri-state answer."""
    requests_mock.get(rm.ANY, json=payload)
    assert fetch_issues_enabled(repo_url) is expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param(_graphql(True), True, id="enabled"),
        pytest.param(_graphql(False), False, id="disabled"),
        pytest.param(_graphql(None), None, id="field-null"),
        pytest.param({"data": {"project": None}}, None, id="project-not-visible"),
        pytest.param({"errors": [{"message": "boom"}]}, None, id="graphql-error"),
    ],
)
def test_fetch_issues_enabled_reads_the_gitlab_flag(
    requests_mock: rm.Mocker, payload: dict[str, Any], expected: bool | None
) -> None:
    """GitLab's `issuesEnabled` maps onto the tri-state answer."""
    requests_mock.post(rm.ANY, json=payload)
    assert fetch_issues_enabled(_GITLAB_URL) is expected


@pytest.mark.parametrize(
    "repo_url",
    [
        pytest.param("https://example.com/example/pkg", id="unsupported-host"),
        pytest.param("https://github.com/example", id="github-without-repo"),
        pytest.param("https://gitlab.com/example", id="gitlab-without-project"),
        pytest.param("https://gist.github.com/example/abc", id="github-subdomain"),
        pytest.param("https://docs.gitlab.com/ee/user", id="gitlab-subdomain"),
    ],
)
def test_fetch_issues_enabled_unresolvable_url_makes_no_request(
    requests_mock: rm.Mocker, repo_url: str
) -> None:
    """A URL no host endpoint can be built from answers unknown without a request."""
    assert fetch_issues_enabled(repo_url) is None
    assert requests_mock.called is False


@pytest.mark.parametrize(
    "repo_url",
    [pytest.param(_GITHUB_URL, id="github"), pytest.param(_GITLAB_URL, id="gitlab")],
)
@pytest.mark.parametrize(
    "status_code",
    [pytest.param(404, id="not-found"), pytest.param(500, id="server-error")],
)
def test_fetch_issues_enabled_api_error_is_unknown(
    requests_mock: rm.Mocker, repo_url: str, status_code: int
) -> None:
    """An API that does not answer yields unknown rather than a verdict."""
    requests_mock.get(rm.ANY, status_code=status_code)
    requests_mock.post(rm.ANY, status_code=status_code)
    assert fetch_issues_enabled(repo_url) is None


@pytest.mark.parametrize(
    "repo_url",
    [pytest.param(_GITHUB_URL, id="github"), pytest.param(_GITLAB_URL, id="gitlab")],
)
def test_fetch_issues_enabled_network_error_is_unknown(
    requests_mock: rm.Mocker, repo_url: str
) -> None:
    """A transport failure yields unknown rather than a verdict."""
    requests_mock.get(rm.ANY, exc=requests.ConnectionError("boom"))
    requests_mock.post(rm.ANY, exc=requests.ConnectionError("boom"))
    assert fetch_issues_enabled(repo_url) is None


@pytest.mark.parametrize(
    ("repo_url", "expected_paths"),
    [
        pytest.param(
            "https://gitlab.com/example/pkg/issues",
            ["example/pkg/issues", "example/pkg"],
            id="legacy-route",
        ),
        pytest.param(
            "https://gitlab.com/example/pkg.git/issues",
            ["example/pkg.git/issues", "example/pkg"],
            id="legacy-route-after-git-suffix",
        ),
    ],
)
def test_fetch_issues_enabled_retries_shorter_gitlab_paths(
    requests_mock: rm.Mocker, repo_url: str, expected_paths: list[str]
) -> None:
    """A legacy GitLab URL keeps its route, so shorter project paths follow."""
    requests_mock.post(
        rm.ANY, [{"json": {"data": {"project": None}}}, {"json": _graphql(True)}]
    )
    assert fetch_issues_enabled(repo_url) is True
    assert [
        request.json()["variables"]["path"] for request in requests_mock.request_history
    ] == expected_paths


def test_fetch_issues_enabled_bounds_gitlab_fallbacks(
    requests_mock: rm.Mocker,
) -> None:
    """An absurdly deep URL from PyPI cannot fan out into unbounded requests."""
    requests_mock.post(rm.ANY, json={"data": {"project": None}})
    deep = "https://gitlab.com/" + "/".join(f"s{index}" for index in range(30))
    assert fetch_issues_enabled(deep) is None
    assert len(requests_mock.request_history) == 4


def test_fetch_issues_enabled_sends_github_token_to_github(
    requests_mock: rm.Mocker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Actions token lifts the anonymous rate limit on the GitHub API."""
    monkeypatch.setenv("GITHUB_TOKEN", "s3cret")
    requests_mock.get(rm.ANY, json={"has_issues": True})
    fetch_issues_enabled(_GITHUB_URL)
    assert requests_mock.last_request.headers["Authorization"] == "Bearer s3cret"


@pytest.mark.parametrize(
    "repo_url",
    [
        pytest.param(_CODEBERG_URL, id="codeberg"),
        pytest.param(_GITLAB_URL, id="gitlab"),
    ],
)
def test_fetch_issues_enabled_withholds_github_token_from_other_hosts(
    requests_mock: rm.Mocker, monkeypatch: pytest.MonkeyPatch, repo_url: str
) -> None:
    """The GitHub token must never be sent to a third-party host."""
    monkeypatch.setenv("GITHUB_TOKEN", "s3cret")
    requests_mock.get(rm.ANY, json={"has_issues": True})
    requests_mock.post(rm.ANY, json=_graphql(True))
    fetch_issues_enabled(repo_url)
    assert "Authorization" not in requests_mock.last_request.headers
