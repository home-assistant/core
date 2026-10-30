"""Tests for script.check_requirements.gate."""

from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import MagicMock

from github import GithubException
import pytest

from script.check_requirements import gate
from script.check_requirements.gate import (
    decide_skip,
    extract_prior_sha,
    fetch_marker_comment_bodies,
)
from script.check_requirements.models import CheckRunResult
from script.check_requirements.render import render_comment

_REPO = "home-assistant/core"
_TOKEN = "test-token"
_PRIOR = "1234567890abcdef1234567890abcdef12345678"
_HEAD = "fedcba0987654321fedcba0987654321fedcba09"

InstallGithub = Callable[..., MagicMock]


def _body(sha: str | None) -> str:
    body = "<!-- requirements-check -->\n## Check requirements\n"
    if sha is not None:
        body += (
            f"\nChecked at commit "
            f"[`{sha[:7]}`](https://github.com/home-assistant/core/commit/{sha})."
        )
    return body


def _comment(
    sha: str | None, *, author: str = "github-actions[bot]"
) -> SimpleNamespace:
    """A PyGithub-like IssueComment with a body and an author login."""
    return SimpleNamespace(body=_body(sha), user=SimpleNamespace(login=author))


def _file(filename: str) -> SimpleNamespace:
    """A PyGithub-like File entry from a commit comparison."""
    return SimpleNamespace(filename=filename)


@pytest.fixture
def install_github(monkeypatch: pytest.MonkeyPatch) -> InstallGithub:
    """Install a fake PyGithub client and return the installer for assertions."""

    def _install(
        *,
        comments: list[SimpleNamespace] | None = None,
        files: list[SimpleNamespace] | None = None,
        comments_exc: Exception | None = None,
        compare_exc: Exception | None = None,
    ) -> MagicMock:
        issue = MagicMock()
        if comments_exc is not None:
            issue.get_comments.side_effect = comments_exc
        else:
            issue.get_comments.return_value = comments or []
        repo = MagicMock()
        repo.get_issue.return_value = issue
        if compare_exc is not None:
            repo.compare.side_effect = compare_exc
        else:
            repo.compare.return_value = SimpleNamespace(files=files or [])
        client = MagicMock()
        client.get_repo.return_value = repo
        monkeypatch.setattr(gate, "Github", lambda **_: client)
        return client

    return _install


@pytest.mark.parametrize(
    ("bodies", "expected"),
    [
        pytest.param([], None, id="no-comments"),
        pytest.param(
            ["<!-- requirements-check -->\nNo commit link here."],
            None,
            id="marker-without-link",
        ),
        pytest.param([_body(_PRIOR)], _PRIOR, id="single-comment"),
        pytest.param([_body(_PRIOR), _body(_HEAD)], _HEAD, id="most-recent-wins"),
    ],
)
def test_extract_prior_sha(bodies: list[str], expected: str | None) -> None:
    """The last recorded commit SHA across marker comments is returned."""
    assert extract_prior_sha(bodies) == expected


def test_extract_prior_sha_normalizes_case() -> None:
    """An upper-case SHA in a link is returned lower-cased."""
    assert extract_prior_sha([_body(_PRIOR.upper())]) == _PRIOR


def test_extract_prior_sha_round_trips_rendered_comment() -> None:
    """The gate reads back exactly the SHA the renderer wrote, keeping them in sync."""
    body = render_comment(CheckRunResult(pr_number=1, head_sha=_HEAD))
    assert extract_prior_sha([body]) == _HEAD


def test_fetch_marker_comment_bodies_returns_all_bot_comments(
    install_github: InstallGithub,
) -> None:
    """Every bot comment body is returned in API order; the marker is not filtered on."""
    install_github(
        comments=[
            _comment(None),  # no SHA recorded yet
            _comment(_PRIOR),
            SimpleNamespace(
                body="chatter", user=SimpleNamespace(login="github-actions[bot]")
            ),
        ]
    )
    bodies = fetch_marker_comment_bodies(7, _REPO, _TOKEN)
    assert bodies == [_body(None), _body(_PRIOR), "chatter"]


@pytest.mark.parametrize(
    "author",
    [
        pytest.param("attacker", id="drive-by-commenter"),
        pytest.param("dependabot[bot]", id="other-bot"),
        pytest.param("maintainer", id="maintainer-account"),
    ],
)
def test_fetch_marker_comment_bodies_ignores_non_actions_author(
    install_github: InstallGithub,
    author: str,
) -> None:
    """A forged marker comment from anyone but github-actions is ignored."""
    install_github(comments=[_comment(_HEAD, author=author)])
    assert fetch_marker_comment_bodies(7, _REPO, _TOKEN) == []


def test_fetch_marker_comment_bodies_handles_api_error(
    install_github: InstallGithub,
) -> None:
    """A GitHub API error yields no bodies (fails open) instead of raising."""
    install_github(comments_exc=GithubException(500, {}, {}))
    assert fetch_marker_comment_bodies(7, _REPO, _TOKEN) == []


def test_decide_skip_no_head_sha(install_github: InstallGithub) -> None:
    """An empty head SHA never skips and makes no API calls."""
    client = install_github()
    assert decide_skip(7, "", _REPO, _TOKEN).skip is False
    client.get_repo.assert_not_called()


def test_decide_skip_no_prior_comment(install_github: InstallGithub) -> None:
    """The first run (no prior comment) runs the checks."""
    install_github(
        comments=[SimpleNamespace(body="hi", user=SimpleNamespace(login="x"))]
    )
    assert decide_skip(7, _HEAD, _REPO, _TOKEN).skip is False


def test_decide_skip_head_unchanged(install_github: InstallGithub) -> None:
    """When head matches the last comment's SHA, skip without comparing."""
    client = install_github(comments=[_comment(_HEAD)])
    assert decide_skip(7, _HEAD, _REPO, _TOKEN).skip is True
    client.get_repo.return_value.compare.assert_not_called()


def test_decide_skip_tracked_files_changed(install_github: InstallGithub) -> None:
    """A requirement file changed since the comment runs the checks."""
    install_github(
        comments=[_comment(_PRIOR)],
        files=[_file("homeassistant/foo.py"), _file("requirements_all.txt")],
    )
    decision = decide_skip(7, _HEAD, _REPO, _TOKEN)
    assert decision.skip is False
    # The untracked file must not be reported as the reason to run.
    assert "requirements_all.txt" in decision.reason
    assert "homeassistant/foo.py" not in decision.reason


def test_decide_skip_no_tracked_files_changed(install_github: InstallGithub) -> None:
    """Only non-requirement files changed since the comment, so skip."""
    install_github(
        comments=[_comment(_PRIOR)],
        files=[_file("homeassistant/components/demo/light.py")],
    )
    assert decide_skip(7, _HEAD, _REPO, _TOKEN).skip is True


def test_decide_skip_compare_unavailable_runs(install_github: InstallGithub) -> None:
    """A failed compare falls back to running the checks."""
    install_github(
        comments=[_comment(_PRIOR)], compare_exc=GithubException(404, {}, {})
    )
    assert decide_skip(7, _HEAD, _REPO, _TOKEN).skip is False


def test_decide_skip_comments_error_runs(install_github: InstallGithub) -> None:
    """A failed comments fetch fails open (runs the checks), never skips."""
    install_github(comments_exc=GithubException(500, {}, {}))
    assert decide_skip(7, _HEAD, _REPO, _TOKEN).skip is False


def test_client_uses_github_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """GHES is supported by passing GITHUB_API_URL (trailing slash stripped)."""
    captured: dict[str, object] = {}
    monkeypatch.setenv("GITHUB_API_URL", "https://ghe.example.com/api/v3/")

    def _fake_github(**kwargs: object) -> MagicMock:
        captured.update(kwargs)
        client = MagicMock()
        client.get_repo.return_value.get_issue.return_value.get_comments.return_value = [
            _comment(_HEAD)
        ]
        return client

    monkeypatch.setattr(gate, "Github", _fake_github)
    assert decide_skip(7, _HEAD, _REPO, _TOKEN).skip is True
    assert captured["base_url"] == "https://ghe.example.com/api/v3"
