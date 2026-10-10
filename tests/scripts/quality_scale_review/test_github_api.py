"""Tests for script.quality_scale_review.github_api."""

from typing import Any

import pytest
import requests_mock as rm

from script.quality_scale_review import github_api

_TOKEN = "test-token"
_REPO = "home-assistant/core"
_PULL_URL = "https://api.github.com/repos/home-assistant/core/pulls/42"
_GRAPHQL_URL = "https://api.github.com/graphql"

_PULL_JSON: dict[str, Any] = {
    "number": 42,
    "title": "Add peblar sensors",
    "body": "Body text",
    "head": {"sha": "abc123"},
    "base": {"ref": "dev"},
    "additions": 30,
    "deletions": 12,
    "changed_files": 3,
}


def test_fetch_pull_request_maps_the_api_fields(requests_mock: rm.Mocker) -> None:
    """The pull request model carries the fields the artifact ships."""
    requests_mock.get(_PULL_URL, json=_PULL_JSON)
    requests_mock.get(
        f"{_PULL_URL}/files",
        json=[
            {"filename": "homeassistant/components/peblar/sensor.py", "status": "added"}
        ],
    )

    pr = github_api.fetch_pull_request(_REPO, 42, _TOKEN)

    assert pr.number == 42
    assert pr.title == "Add peblar sensors"
    assert pr.body == "Body text"
    assert pr.head_sha == "abc123"
    assert pr.base_ref == "dev"
    assert pr.changed_lines == 42
    assert pr.changed_files == 3
    assert pr.file_statuses == {"homeassistant/components/peblar/sensor.py": "added"}
    assert pr.filenames == ["homeassistant/components/peblar/sensor.py"]


def test_fetch_pull_request_reads_an_empty_body_as_a_string(
    requests_mock: rm.Mocker,
) -> None:
    """A pull request without a description has no body in the API response."""
    requests_mock.get(_PULL_URL, json=_PULL_JSON | {"body": None})
    requests_mock.get(f"{_PULL_URL}/files", json=[])

    assert github_api.fetch_pull_request(_REPO, 42, _TOKEN).body == ""


def test_fetch_pull_request_follows_the_file_pages(requests_mock: rm.Mocker) -> None:
    """Changed files are paginated; every page contributes its filenames."""
    requests_mock.get(_PULL_URL, json=_PULL_JSON)
    requests_mock.get(
        f"{_PULL_URL}/files",
        json=[{"filename": "first.py", "status": "modified"}],
        headers={"Link": f'<{_PULL_URL}/files?page=2>; rel="next"'},
    )
    requests_mock.get(
        f"{_PULL_URL}/files?page=2",
        json=[{"filename": "second.py", "status": "removed"}],
    )

    pr = github_api.fetch_pull_request(_REPO, 42, _TOKEN)

    assert pr.filenames == ["first.py", "second.py"]


def test_fetch_diff_requests_the_diff_media_type(requests_mock: rm.Mocker) -> None:
    """The diff comes from the pull request endpoint as raw text."""
    requests_mock.get(_PULL_URL, text="diff --git a/x b/x\n")

    assert github_api.fetch_diff(_REPO, 42, _TOKEN) == "diff --git a/x b/x\n"
    assert (
        requests_mock.last_request.headers["Accept"] == "application/vnd.github.v3.diff"
    )


def test_graphql_returns_the_data_payload(requests_mock: rm.Mocker) -> None:
    """A successful query returns its `data` payload."""
    requests_mock.post(_GRAPHQL_URL, json={"data": {"repository": {}}})

    assert github_api.graphql("query {}", _TOKEN) == {"repository": {}}


def test_graphql_raises_on_query_errors(requests_mock: rm.Mocker) -> None:
    """GraphQL reports query errors with a 200 response."""
    requests_mock.post(
        _GRAPHQL_URL, json={"data": None, "errors": [{"message": "Bad query"}]}
    )

    with pytest.raises(RuntimeError, match="Bad query"):
        github_api.graphql("query {}", _TOKEN)
