"""Data models for the deterministic requirements check."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CheckStatus(StrEnum):
    """Outcome of a single check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NEEDS_AGENT = "needs_agent"


class CheckKind(StrEnum):
    """The set of checks the deterministic stage can produce.

    The agent prompt has one instruction section per kind. Adding a new kind
    here requires adding the corresponding section in the agent prompt;
    otherwise the agent will fail hard when it encounters the new kind.
    """

    REPO_PUBLIC = "repo_public"
    CI_UPLOAD = "ci_upload"
    RELEASE_PIPELINE = "release_pipeline"
    PR_LINK = "pr_link"
    ASYNC_BLOCKING = "async_blocking"
    YANKED = "yanked"
    VULNERABILITIES = "vulnerabilities"


@dataclass(slots=True)
class CheckResult:
    """Result of a single check (deterministic or pending agent)."""

    status: CheckStatus
    details: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable representation of this check result."""
        return {"status": self.status.value, "details": self.details}


@dataclass(slots=True)
class PackageChange:
    """A package change identified from the diff plus its check results.

    `old_version` is `None` for a newly added package; otherwise it is a
    version bump. `checks` is keyed by `CheckKind`. A missing entry means
    the check did not run for this package (e.g. a check whose prerequisite
    was unmet); the renderer displays such checks as skipped (—).
    """

    name: str
    old_version: str | None
    new_version: str

    repo_url: str | None = None
    publisher_kind: str | None = None
    checks: dict[CheckKind, CheckResult] = field(default_factory=dict)

    @property
    def needs_agent(self) -> bool:
        """Return True when any of this package's checks needs LLM judgement."""
        return any(c.status == CheckStatus.NEEDS_AGENT for c in self.checks.values())

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of this package change."""
        return {
            "name": self.name,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "repo_url": self.repo_url,
            "publisher_kind": self.publisher_kind,
            "checks": {
                kind.value: result.to_dict() for kind, result in self.checks.items()
            },
            "needs_agent": self.needs_agent,
        }


@dataclass(slots=True)
class CheckRunResult:
    """The full deterministic check result for a PR."""

    pr_number: int
    packages: list[PackageChange] = field(default_factory=list)
    rendered_comment: str = ""

    @property
    def needs_agent(self) -> bool:
        """Return True when any package in this run still needs LLM judgement."""
        return any(p.needs_agent for p in self.packages)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of this check run."""
        return {
            "version": 1,
            "pr_number": self.pr_number,
            "needs_agent": self.needs_agent,
            "packages": [p.to_dict() for p in self.packages],
            "rendered_comment": self.rendered_comment,
        }
