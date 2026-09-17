"""Data models for the deterministic quality scale review stage."""

from dataclasses import asdict, dataclass
import re
from typing import Any

# Frontmatter title of a rule documentation page, quoted or unquoted.
_TITLE = re.compile(r'^title:\s*"?([^"\n]*)"?', re.MULTILINE)


@dataclass(slots=True, frozen=True)
class PullRequest:
    """The pull request data the reviewer needs."""

    number: int
    title: str
    body: str
    head_sha: str
    base_ref: str
    additions: int
    deletions: int
    changed_files: int
    file_statuses: dict[str, str]
    """Changed file paths mapped to their GitHub API `status`."""

    @property
    def filenames(self) -> list[str]:
        """Return the paths of the changed files."""
        return list(self.file_statuses)

    @property
    def changed_lines(self) -> int:
        """Return the number of added plus deleted lines."""
        return self.additions + self.deletions

    def to_meta_dict(self) -> dict[str, Any]:
        """Return the `pr-meta.json` payload."""
        return {
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "headRefOid": self.head_sha,
            "baseRefName": self.base_ref,
            "additions": self.additions,
            "deletions": self.deletions,
            "changedFiles": self.changed_files,
        }


@dataclass(slots=True, frozen=True)
class RuleDoc:
    """A rule documentation page of the Integration Quality Scale."""

    filename: str
    text: str

    @property
    def rule(self) -> str:
        """Return the rule id, which is the file name without its extension."""
        return self.filename.removesuffix(".md")

    @property
    def title(self) -> str:
        """Return the frontmatter title, empty when the page has none."""
        match = _TITLE.search(self.text)
        return match.group(1) if match else ""


@dataclass(slots=True, frozen=True)
class Results:
    """The `results.json` payload consumed by the agentic stage."""

    pr_number: int
    head_sha: str
    skip: bool
    too_long: bool
    skip_reason: str
    changed_lines: int
    changed_files: int
    domains: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of these results."""
        return asdict(self)
