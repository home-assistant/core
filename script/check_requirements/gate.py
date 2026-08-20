"""Decide whether the deterministic stage can skip re-checking a PR.

The stage re-runs on every `synchronize` where the PR touches a tracked
requirement file, so it compares the pin changes the PR proposes against the
ones the last comment reported; matching means skip the PyPI work and flag the
artifact so the agentic stage no-ops. Merging the base branch into the PR moves
head and drags in unrelated requirement bumps, but leaves the PR's pins alone.
"""

from dataclasses import dataclass
import logging
import os
import re

from github import Auth, Github, GithubException
from github.IssueComment import IssueComment

from .diff import canonical_name
from .models import PackageChange
from .render import COMMIT_PATH, MARKER, SKIPPED

_LOGGER = logging.getLogger(__name__)

# The "Checked at commit [`abc1234`](...COMMIT_PATH<40-hex>)." link rendered by
# render._intro is the only place the head SHA is recorded in the comment.
_COMMIT_SHA_RE = re.compile(re.escape(COMMIT_PATH) + r"([0-9a-f]{40})", re.IGNORECASE)
_TRUSTED_AUTHOR = "github-actions[bot]"

# The first three columns of the table rendered by render._table; the agent
# rewrites only the check cells to their right.
_PIN_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", re.MULTILINE
)
_PIN_TABLE_HEADER = ("Package", "Old", "New")
_PIN_TABLE_RULE = "---"

# Canonical package name, old version (None when the package is new), new version.
type Pin = tuple[str, str | None, str]


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


def pin_set(changes: list[PackageChange]) -> set[Pin]:
    """Return the pin changes of a run in comparable form."""
    return {
        (canonical_name(change.name), change.old_version, change.new_version)
        for change in changes
    }


def extract_prior_pins(bodies: list[str]) -> set[Pin]:
    """Return the pin changes recorded in the most recent marker comment."""
    body = next((body for body in reversed(bodies) if MARKER in body), "")
    pins: set[Pin] = set()
    for name, old, new in _PIN_ROW_RE.findall(body):
        if (name, old, new) == _PIN_TABLE_HEADER or name == _PIN_TABLE_RULE:
            continue
        pins.add((canonical_name(name), None if old == SKIPPED else old, new))
    return pins


def _label(pin: Pin) -> str:
    """Describe one pin change for the decision reason."""
    name, old, new = pin
    return f"{name} {old} → {new}" if old else f"{name} {new} (new)"


def decide_skip(
    pr_number: int, head_sha: str, repo: str, token: str, current: set[Pin]
) -> GateDecision:
    """Decide whether the PR's pin changes differ from the last comment's."""
    if not head_sha:
        return GateDecision(False, "No head SHA available; running checks.")
    bodies = fetch_marker_comment_bodies(pr_number, repo, token)
    prior_sha = extract_prior_sha(bodies)
    if prior_sha is None:
        return GateDecision(
            False, "No previous requirements-check comment; running checks."
        )
    if prior_sha == head_sha.lower():
        return GateDecision(
            True, f"Head {head_sha} unchanged since the last comment; skipping."
        )
    prior = extract_prior_pins(bodies)
    if prior == current:
        return GateDecision(True, f"Pin changes unchanged since {prior_sha}; skipping.")
    delta = ", ".join(sorted(_label(pin) for pin in prior ^ current))
    return GateDecision(
        False, f"Pin changes differ from {prior_sha} ({delta}); running checks."
    )
