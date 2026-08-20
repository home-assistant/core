"""Tests for script.check_requirements.gate."""

from collections.abc import Callable
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

from github import GithubException
import pytest

from script.check_requirements import gate
from script.check_requirements.diff import parse_diff
from script.check_requirements.gate import (
    Pin,
    decide_skip,
    extract_prior_pins,
    extract_prior_sha,
    fetch_marker_comment_bodies,
    pin_set,
)
from script.check_requirements.models import (
    CheckKind,
    CheckResult,
    CheckRunResult,
    CheckStatus,
    PackageChange,
)
from script.check_requirements.render import render_comment

_REPO = "home-assistant/core"
_TOKEN = "test-token"
_PRIOR = "1234567890abcdef1234567890abcdef12345678"
_HEAD = "fedcba0987654321fedcba0987654321fedcba09"

InstallGithub = Callable[..., MagicMock]


def _pkg(name: str, old: str | None, new: str) -> PackageChange:
    """A package change as the diff parser would report it."""
    return PackageChange(name=name, old_version=old, new_version=new)


def _body(sha: str | None, *packages: PackageChange) -> str:
    """A comment body exactly as the renderer produces it."""
    return render_comment(
        CheckRunResult(pr_number=7, head_sha=sha, packages=list(packages))
    )


def _comment(
    sha: str | None, *packages: PackageChange, author: str = "github-actions[bot]"
) -> SimpleNamespace:
    """A PyGithub-like IssueComment with a body and an author login."""
    return SimpleNamespace(
        body=_body(sha, *packages), user=SimpleNamespace(login=author)
    )


@pytest.fixture
def install_github(monkeypatch: pytest.MonkeyPatch) -> InstallGithub:
    """Install a fake PyGithub client and return the installer for assertions."""

    def _install(
        *,
        comments: list[SimpleNamespace] | None = None,
        comments_exc: Exception | None = None,
    ) -> MagicMock:
        issue = MagicMock()
        if comments_exc is not None:
            issue.get_comments.side_effect = comments_exc
        else:
            issue.get_comments.return_value = comments or []
        repo = MagicMock()
        repo.get_issue.return_value = issue
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
    assert extract_prior_sha([_body(_HEAD)]) == _HEAD


@pytest.mark.parametrize(
    ("packages", "expected"),
    [
        pytest.param([], set(), id="no-pin-changes"),
        pytest.param(
            [_pkg("pkg", "1.0.0", "1.1.0")],
            {("pkg", "1.0.0", "1.1.0")},
            id="version-bump",
        ),
        pytest.param(
            [_pkg("pkg", None, "1.0.0")],
            {("pkg", None, "1.0.0")},
            id="new-package",
        ),
        pytest.param(
            [_pkg("Foo_Bar", "1.0.0", "2.0.0"), _pkg("other", None, "0.1")],
            {("foo-bar", "1.0.0", "2.0.0"), ("other", None, "0.1")},
            id="canonical-names",
        ),
    ],
)
def test_extract_prior_pins_round_trips_rendered_table(
    packages: list[PackageChange], expected: set[Pin]
) -> None:
    """The pins parsed back out of a comment match the ones rendered into it."""
    body = _body(_PRIOR, *packages)
    assert extract_prior_pins([body]) == expected
    assert pin_set(packages) == expected


def test_extract_prior_pins_reads_back_an_agent_posted_comment() -> None:
    """The pins survive the agent filling its placeholders in the real comment."""
    package = _pkg("pkg", "1.0.0", "1.1.0")
    package.checks[CheckKind.YANKED] = CheckResult(CheckStatus.PASS, "live release")
    package.checks[CheckKind.SECURITY] = CheckResult(CheckStatus.NEEDS_AGENT, "todo")
    posted = re.sub(
        r"\{\{(CHECK_CELL|CHECK_DETAIL|SUMMARY)[^}]*\}\}",
        "☑️",
        _body(_PRIOR, package),
    )
    assert extract_prior_pins([posted]) == {("pkg", "1.0.0", "1.1.0")}


def test_extract_prior_pins_handles_crlf_bodies() -> None:
    """GitHub serves comment bodies with CRLF line endings; rows still parse."""
    body = _body(_PRIOR, _pkg("pkg", "1.0.0", "1.1.0")).replace("\n", "\r\n")
    assert extract_prior_pins([body]) == {("pkg", "1.0.0", "1.1.0")}


def test_extract_prior_pins_uses_most_recent_marker_comment() -> None:
    """Only the newest check comment describes the current state of the PR."""
    bodies = [
        _body(_PRIOR, _pkg("pkg", "1.0.0", "1.1.0")),
        "unrelated bot chatter",
        _body(_HEAD, _pkg("pkg", "1.0.0", "1.2.0")),
    ]
    assert extract_prior_pins(bodies) == {("pkg", "1.0.0", "1.2.0")}


def test_pin_set_from_parsed_diff() -> None:
    """The gate's comparison key is derived straight from the parsed diff."""
    diff_text = (
        "diff --git a/requirements_all.txt b/requirements_all.txt\n"
        "--- a/requirements_all.txt\n"
        "+++ b/requirements_all.txt\n"
        "@@ -1,2 +1,3 @@\n"
        "-pkg==1.0.0\n"
        "+pkg==1.1.0\n"
        "+brand-new==0.1.0\n"
        " unchanged==2.0.0\n"
    )
    assert pin_set(parse_diff(diff_text)) == {
        ("pkg", "1.0.0", "1.1.0"),
        ("brand-new", None, "0.1.0"),
    }


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
    assert decide_skip(7, "", _REPO, _TOKEN, set()).skip is False
    client.get_repo.assert_not_called()


def test_decide_skip_no_prior_comment(install_github: InstallGithub) -> None:
    """The first run (no prior comment) runs the checks."""
    install_github(
        comments=[SimpleNamespace(body="hi", user=SimpleNamespace(login="x"))]
    )
    assert decide_skip(7, _HEAD, _REPO, _TOKEN, set()).skip is False


def test_decide_skip_head_unchanged(install_github: InstallGithub) -> None:
    """When head matches the last comment's SHA, skip without reading the table."""
    install_github(comments=[_comment(_HEAD)])
    decision = decide_skip(7, _HEAD, _REPO, _TOKEN, {("pkg", "1.0.0", "1.1.0")})
    assert decision.skip is True
    assert _HEAD in decision.reason


def test_decide_skip_pins_unchanged_after_base_merge(
    install_github: InstallGithub,
) -> None:
    """Merging the base branch moves head without touching the PR's own pins."""
    install_github(comments=[_comment(_PRIOR, _pkg("pkg", "1.0.0", "1.1.0"))])
    decision = decide_skip(7, _HEAD, _REPO, _TOKEN, {("pkg", "1.0.0", "1.1.0")})
    assert decision.skip is True
    assert _PRIOR in decision.reason


def test_decide_skip_no_pins_on_either_side(install_github: InstallGithub) -> None:
    """A PR that never changed a pin stays skipped as head moves on."""
    install_github(comments=[_comment(_PRIOR)])
    assert decide_skip(7, _HEAD, _REPO, _TOKEN, set()).skip is True


@pytest.mark.parametrize(
    ("prior_packages", "current", "expected_in_reason"),
    [
        pytest.param(
            [_pkg("pkg", "1.0.0", "1.1.0")],
            {("pkg", "1.0.0", "1.2.0")},
            ["pkg 1.0.0 → 1.1.0", "pkg 1.0.0 → 1.2.0"],
            id="version-repinned",
        ),
        pytest.param(
            [_pkg("pkg", "1.0.0", "1.1.0")],
            set(),
            ["pkg 1.0.0 → 1.1.0"],
            id="pin-change-reverted",
        ),
        pytest.param(
            [],
            {("brand-new", None, "0.1.0")},
            ["brand-new 0.1.0 (new)"],
            id="pin-change-added",
        ),
    ],
)
def test_decide_skip_pins_changed(
    install_github: InstallGithub,
    prior_packages: list[PackageChange],
    current: set[Pin],
    expected_in_reason: list[str],
) -> None:
    """Different pin changes than the last comment reported run the checks."""
    install_github(comments=[_comment(_PRIOR, *prior_packages)])
    decision = decide_skip(7, _HEAD, _REPO, _TOKEN, current)
    assert decision.skip is False
    for expected in expected_in_reason:
        assert expected in decision.reason


def test_decide_skip_comments_error_runs(install_github: InstallGithub) -> None:
    """A failed comments fetch fails open (runs the checks), never skips."""
    install_github(comments_exc=GithubException(500, {}, {}))
    assert decide_skip(7, _HEAD, _REPO, _TOKEN, set()).skip is False


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
    assert decide_skip(7, _HEAD, _REPO, _TOKEN, set()).skip is True
    assert captured["base_url"] == "https://ghe.example.com/api/v3"
