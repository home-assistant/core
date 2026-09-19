"""Read pull request data and repository files from the GitHub API."""

from collections.abc import Iterator
import os
from typing import Any

import requests

from .models import PullRequest

_TIMEOUT = 30
_JSON = "application/vnd.github+json"
_DIFF = "application/vnd.github.v3.diff"


def _session(token: str, accept: str = _JSON) -> requests.Session:
    """Return a session authenticated for the GitHub API."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return session


def _rest_url(*parts: str) -> str:
    """Return the REST API URL of a path below the API root."""
    root = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    return "/".join([root, *parts])


def _paginate(session: requests.Session, url: str) -> Iterator[dict[str, Any]]:
    """Yield every item of a paginated list endpoint."""
    params: dict[str, Any] | None = {"per_page": 100}
    while url:
        response = session.get(url, params=params, timeout=_TIMEOUT)
        response.raise_for_status()
        yield from response.json()
        url = response.links.get("next", {}).get("url", "")
        params = None


def fetch_pull_request(repo: str, number: int, token: str) -> PullRequest:
    """Return the pull request metadata and the names of its changed files."""
    session = _session(token)
    url = _rest_url("repos", repo, "pulls", str(number))
    response = session.get(url, timeout=_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    return PullRequest(
        number=data["number"],
        title=data["title"],
        body=data["body"] or "",
        head_sha=data["head"]["sha"],
        base_ref=data["base"]["ref"],
        additions=data["additions"],
        deletions=data["deletions"],
        changed_files=data["changed_files"],
        file_statuses={
            file["filename"]: file["status"]
            for file in _paginate(session, f"{url}/files")
        },
    )


def fetch_diff(repo: str, number: int, token: str) -> str:
    """Return the unified diff of the pull request."""
    response = _session(token, accept=_DIFF).get(
        _rest_url("repos", repo, "pulls", str(number)), timeout=_TIMEOUT
    )
    response.raise_for_status()
    return response.text


def graphql(query: str, token: str) -> dict[str, Any]:
    """Run a GraphQL query and return its `data` payload."""
    url = os.environ.get("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql")
    response = _session(token).post(url, json={"query": query}, timeout=_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if errors := payload.get("errors"):
        raise RuntimeError(f"GraphQL query failed: {errors}")
    return payload["data"]
