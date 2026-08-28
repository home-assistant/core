"""Decide whether the deterministic stage can skip re-checking a PR.

The deterministic stage re-runs on every `synchronize` where the PR touches a
tracked requirement file, even when the latest push changed only unrelated
files. This module answers "did a tracked requirement file actually change
since we last commented?" so the stage can skip the PyPI work and flag the
uploaded artifact as skipped, telling the agentic stage to no-op.
"""

from dataclasses import dataclass
import logging
import os
import re

from github import Auth, Github, GithubException
from github.IssueComment import IssueComment

from .diff import is_tracked
from .render import COMMIT_PATH

_LOGGER = logging.getLogger(__name__)

# The "Checked at commit [`abc1234`](...COMMIT_PATH<40-hex>)." link rendered by
# render._intro is the only place the head SHA is recorded in the comment.
_COMMIT_SHA_RE = re.compile(re.escape(COMMIT_PATH) + r"([0-9a-f]{40})", re.IGNORECASE)
_TRUSTED_AUTHOR = "github-actions[bot]"


def _is_trusted_author(comment: IssueComment) -> bool:
    """True only for the github-actions bot that posts the check comment."""
    return comment.user is not None and comment.user.login == _TRUSTED_AUTHOR


@dataclass(slots=True, frozen=True)
class GateDecision:
    """Whether to skip the deterministic checks, with a human-readable reason."""

    skip: bool
    reason: str


def _client(token: str) -> Github:
    """A lazy GitHub client on the configured (possibly GHES) API base."""
    base_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    return Github(auth=Auth.Token(token), base_url=base_url, lazy=True)


def fetch_marker_comment_bodies(pr_number: int, repo: str, token: str) -> list[str]:
    """Return the trusted requirements-check comment bodies, oldest-first."""
    try:
        comments = _client(token).get_repo(repo).get_issue(pr_number).get_comments()
        return [comment.body for comment in comments if _is_trusted_author(comment)]
    except GithubException as err:
        _LOGGER.warning("Could not read comments for PR #%s: %s", pr_number, err)
        return []


def extract_prior_sha(bodies: list[str]) -> str | None:
    """Return the head SHA recorded in the most recent marker comment."""
    shas = [
        match.group(1).lower()
        for body in bodies
        for match in _COMMIT_SHA_RE.finditer(body)
    ]
    return shas[-1] if shas else None


def compare_changed_files(
    base: str, head: str, repo: str, token: str
) -> list[str] | None:
    """Return filenames changed between two commits, or None if unavailable."""
    try:
        comparison = _client(token).get_repo(repo).compare(base, head)
        return [changed.filename for changed in comparison.files]
    except GithubException as err:
        _LOGGER.warning("Could not compare %s...%s: %s", base, head, err)
        return None


def decide_skip(pr_number: int, head_sha: str, repo: str, token: str) -> GateDecision:
    """Decide whether requirements changed since the last comment."""
    if not head_sha:
        return GateDecision(False, "No head SHA available; running checks.")
    prior = extract_prior_sha(fetch_marker_comment_bodies(pr_number, repo, token))
    if prior is None:
        return GateDecision(
            False, "No previous requirements-check comment; running checks."
        )
    if prior == head_sha.lower():
        return GateDecision(
            True, f"Head {head_sha} unchanged since the last comment; skipping."
        )
    changed = compare_changed_files(prior, head_sha, repo, token)
    if changed is None:
        return GateDecision(
            False, f"Could not compare {prior}...{head_sha}; running checks."
        )
    tracked = [path for path in changed if is_tracked(path)]
    if tracked:
        return GateDecision(
            False,
            f"Tracked requirement files changed since {prior}; running checks: "
            + ", ".join(tracked),
        )
    return GateDecision(
        True, f"No tracked requirement files changed since {prior}; skipping."
    )
