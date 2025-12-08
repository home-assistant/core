"""Issue functions for Home Assistant templates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry as ir

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class IssuesExtension(BaseTemplateExtension):
    """Extension for issue-related template functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the issues extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "issues",
                    self.issues,
                    as_global=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "issue",
                    self.issue,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
            ],
        )

    def issues(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Return all open issues."""
        current_issues = ir.async_get(self.hass).issues
        # Use JSON for safe representation
        return {
            key: issue_entry.to_json()
            for (key, issue_entry) in current_issues.items()
            if issue_entry.active
        }

    def issue(self, domain: str, issue_id: str) -> dict[str, Any] | None:
        """Get issue by domain and issue_id."""
        result = ir.async_get(self.hass).async_get_issue(domain, issue_id)
        if result:
            return result.to_json()
        return None
