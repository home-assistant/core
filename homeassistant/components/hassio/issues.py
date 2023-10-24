"""Supervisor events monitor."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any, NotRequired, TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import (
    ATTR_DATA,
    ATTR_HEALTHY,
    ATTR_ISSUES,
    ATTR_SUGGESTIONS,
    ATTR_SUPPORTED,
    ATTR_UNHEALTHY,
    ATTR_UNHEALTHY_REASONS,
    ATTR_UNSUPPORTED,
    ATTR_UNSUPPORTED_REASONS,
    ATTR_UPDATE_KEY,
    ATTR_WS_EVENT,
    DOMAIN,
    EVENT_HEALTH_CHANGED,
    EVENT_ISSUE_CHANGED,
    EVENT_ISSUE_REMOVED,
    EVENT_SUPERVISOR_EVENT,
    EVENT_SUPERVISOR_UPDATE,
    EVENT_SUPPORTED_CHANGED,
    ISSUE_KEY_SYSTEM_DOCKER_CONFIG,
    PLACEHOLDER_KEY_REFERENCE,
    UPDATE_KEY_SUPERVISOR,
    SupervisorIssueContext,
)
from .handler import HassIO, HassioAPIError

ISSUE_KEY_UNHEALTHY = "unhealthy"
ISSUE_KEY_UNSUPPORTED = "unsupported"
ISSUE_ID_UNHEALTHY = "unhealthy_system"
ISSUE_ID_UNSUPPORTED = "unsupported_system"

INFO_URL_UNHEALTHY = "https://www.home-assistant.io/more-info/unhealthy"
INFO_URL_UNSUPPORTED = "https://www.home-assistant.io/more-info/unsupported"

PLACEHOLDER_KEY_REASON = "reason"

UNSUPPORTED_REASONS = {
    "apparmor",
    "connectivity_check",
    "content_trust",
    "dbus",
    "dns_server",
    "docker_configuration",
    "docker_version",
    "cgroup_version",
    "job_conditions",
    "lxc",
    "network_manager",
    "os",
    "os_agent",
    "restart_policy",
    "software",
    "source_mods",
    "supervisor_version",
    "systemd",
    "systemd_journal",
    "systemd_resolved",
}
# Some unsupported reasons also mark the system as unhealthy. If the unsupported reason
# provides no additional information beyond the unhealthy one then skip that repair.
UNSUPPORTED_SKIP_REPAIR = {"privileged"}
UNHEALTHY_REASONS = {
    "docker",
    "supervisor",
    "setup",
    "privileged",
    "untrusted",
}

# Keys (type + context) of issues that when found should be made into a repair
ISSUE_KEYS_FOR_REPAIRS = {
    "issue_mount_mount_failed",
    "issue_system_multiple_data_disks",
    "issue_system_reboot_required",
    ISSUE_KEY_SYSTEM_DOCKER_CONFIG,
}

_LOGGER = logging.getLogger(__name__)


class SuggestionDataType(TypedDict):
    """Suggestion dictionary as received from supervisor."""

    uuid: str
    type: str
    context: str
    reference: str | None


@dataclass(slots=True, frozen=True)
class Suggestion:
    """Suggestion from Supervisor which resolves an issue."""

    uuid: str
    type: str
    context: SupervisorIssueContext
    reference: str | None = None

    @property
    def key(self) -> str:
        """Get key for suggestion (combination of context and type)."""
        return f"{self.context}_{self.type}"

    @classmethod
    def from_dict(cls, data: SuggestionDataType) -> Suggestion:
        """Convert from dictionary representation."""
        return cls(
            uuid=data["uuid"],
            type=data["type"],
            context=SupervisorIssueContext(data["context"]),
            reference=data["reference"],
        )


class IssueDataType(TypedDict):
    """Issue dictionary as received from supervisor."""

    uuid: str
    type: str
    context: str
    reference: str | None
    suggestions: NotRequired[list[SuggestionDataType]]


@dataclass(slots=True, frozen=True)
class Issue:
    """Issue from Supervisor."""

    uuid: str
    type: str
    context: SupervisorIssueContext
    reference: str | None = None
    suggestions: list[Suggestion] = field(default_factory=list, compare=False)

    @property
    def key(self) -> str:
        """Get key for issue (combination of context and type)."""
        return f"issue_{self.context}_{self.type}"

    @classmethod
    def from_dict(cls, data: IssueDataType) -> Issue:
        """Convert from dictionary representation."""
        suggestions: list[SuggestionDataType] = data.get("suggestions", [])
        return cls(
            uuid=data["uuid"],
            type=data["type"],
            context=SupervisorIssueContext(data["context"]),
            reference=data["reference"],
            suggestions=[
                Suggestion.from_dict(suggestion) for suggestion in suggestions
            ],
        )


class SupervisorIssues:
    """Create issues from supervisor events."""

    def __init__(self, hass: HomeAssistant, client: HassIO) -> None:
        """Initialize supervisor issues."""
        self._hass = hass
        self._client = client
        self._unsupported_reasons: set[str] = set()
        self._unhealthy_reasons: set[str] = set()
        self._issues: dict[str, Issue] = {}

    @property
    def unhealthy_reasons(self) -> set[str]:
        """Get unhealthy reasons. Returns empty set if system is healthy."""
        return self._unhealthy_reasons

    @unhealthy_reasons.setter
    def unhealthy_reasons(self, reasons: set[str]) -> None:
        """Set unhealthy reasons. Create or delete repairs as necessary."""
        for unhealthy in reasons - self.unhealthy_reasons:
            if unhealthy in UNHEALTHY_REASONS:
                translation_key = f"{ISSUE_KEY_UNHEALTHY}_{unhealthy}"
                translation_placeholders = None
            else:
                translation_key = ISSUE_KEY_UNHEALTHY
                translation_placeholders = {PLACEHOLDER_KEY_REASON: unhealthy}

            async_create_issue(
                self._hass,
                DOMAIN,
                f"{ISSUE_ID_UNHEALTHY}_{unhealthy}",
                is_fixable=False,
                learn_more_url=f"{INFO_URL_UNHEALTHY}/{unhealthy}",
                severity=IssueSeverity.CRITICAL,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )

        for fixed in self.unhealthy_reasons - reasons:
            async_delete_issue(self._hass, DOMAIN, f"{ISSUE_ID_UNHEALTHY}_{fixed}")

        self._unhealthy_reasons = reasons

    @property
    def unsupported_reasons(self) -> set[str]:
        """Get unsupported reasons. Returns empty set if system is supported."""
        return self._unsupported_reasons

    @unsupported_reasons.setter
    def unsupported_reasons(self, reasons: set[str]) -> None:
        """Set unsupported reasons. Create or delete repairs as necessary."""
        for unsupported in reasons - UNSUPPORTED_SKIP_REPAIR - self.unsupported_reasons:
            if unsupported in UNSUPPORTED_REASONS:
                translation_key = f"{ISSUE_KEY_UNSUPPORTED}_{unsupported}"
                translation_placeholders = None
            else:
                translation_key = ISSUE_KEY_UNSUPPORTED
                translation_placeholders = {PLACEHOLDER_KEY_REASON: unsupported}

            async_create_issue(
                self._hass,
                DOMAIN,
                f"{ISSUE_ID_UNSUPPORTED}_{unsupported}",
                is_fixable=False,
                learn_more_url=f"{INFO_URL_UNSUPPORTED}/{unsupported}",
                severity=IssueSeverity.WARNING,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )

        for fixed in self.unsupported_reasons - (reasons - UNSUPPORTED_SKIP_REPAIR):
            async_delete_issue(self._hass, DOMAIN, f"{ISSUE_ID_UNSUPPORTED}_{fixed}")

        self._unsupported_reasons = reasons

    @property
    def issues(self) -> set[Issue]:
        """Get issues."""
        return set(self._issues.values())

    def add_issue(self, issue: Issue) -> None:
        """Add or update an issue in the list. Create or update a repair if necessary."""
        if issue.key in ISSUE_KEYS_FOR_REPAIRS:
            placeholders: dict[str, str] | None = None
            if issue.reference:
                placeholders = {PLACEHOLDER_KEY_REFERENCE: issue.reference}
            async_create_issue(
                self._hass,
                DOMAIN,
                issue.uuid,
                is_fixable=bool(issue.suggestions),
                severity=IssueSeverity.WARNING,
                translation_key=issue.key,
                translation_placeholders=placeholders,
            )

        self._issues[issue.uuid] = issue

    async def add_issue_from_data(self, data: IssueDataType) -> None:
        """Add issue from data to list after getting latest suggestions."""
        try:
            data["suggestions"] = (
                await self._client.get_suggestions_for_issue(data["uuid"])
            )[ATTR_SUGGESTIONS]
        except HassioAPIError:
            _LOGGER.error(
                "Could not get suggestions for supervisor issue %s, skipping it",
                data["uuid"],
            )
            return
        self.add_issue(Issue.from_dict(data))

    def remove_issue(self, issue: Issue) -> None:
        """Remove an issue from the list. Delete a repair if necessary."""
        if issue.uuid not in self._issues:
            return

        if issue.key in ISSUE_KEYS_FOR_REPAIRS:
            async_delete_issue(self._hass, DOMAIN, issue.uuid)

        del self._issues[issue.uuid]

    def get_issue(self, issue_id: str) -> Issue | None:
        """Get issue from key."""
        return self._issues.get(issue_id)

    async def setup(self) -> None:
        """Create supervisor events listener."""
        await self.update()

        async_dispatcher_connect(
            self._hass, EVENT_SUPERVISOR_EVENT, self._supervisor_events_to_issues
        )

    async def update(self) -> None:
        """Update issues from Supervisor resolution center."""
        try:
            data = await self._client.get_resolution_info()
        except HassioAPIError as err:
            _LOGGER.error("Failed to update supervisor issues: %r", err)
            return
        self.unhealthy_reasons = set(data[ATTR_UNHEALTHY])
        self.unsupported_reasons = set(data[ATTR_UNSUPPORTED])

        # Remove any cached issues that weren't returned
        for issue_id in set(self._issues.keys()) - {
            issue["uuid"] for issue in data[ATTR_ISSUES]
        }:
            self.remove_issue(self._issues[issue_id])

        # Add/update any issues that came back
        await asyncio.gather(
            *[self.add_issue_from_data(issue) for issue in data[ATTR_ISSUES]]
        )

    @callback
    def _supervisor_events_to_issues(self, event: dict[str, Any]) -> None:
        """Create issues from supervisor events."""
        if ATTR_WS_EVENT not in event:
            return

        if (
            event[ATTR_WS_EVENT] == EVENT_SUPERVISOR_UPDATE
            and event.get(ATTR_UPDATE_KEY) == UPDATE_KEY_SUPERVISOR
        ):
            self._hass.async_create_task(self.update())

        elif event[ATTR_WS_EVENT] == EVENT_HEALTH_CHANGED:
            self.unhealthy_reasons = (
                set()
                if event[ATTR_DATA][ATTR_HEALTHY]
                else set(event[ATTR_DATA][ATTR_UNHEALTHY_REASONS])
            )

        elif event[ATTR_WS_EVENT] == EVENT_SUPPORTED_CHANGED:
            self.unsupported_reasons = (
                set()
                if event[ATTR_DATA][ATTR_SUPPORTED]
                else set(event[ATTR_DATA][ATTR_UNSUPPORTED_REASONS])
            )

        elif event[ATTR_WS_EVENT] == EVENT_ISSUE_CHANGED:
            self.add_issue(Issue.from_dict(event[ATTR_DATA]))

        elif event[ATTR_WS_EVENT] == EVENT_ISSUE_REMOVED:
            self.remove_issue(Issue.from_dict(event[ATTR_DATA]))
