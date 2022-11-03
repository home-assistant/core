"""Supervisor events monitor."""
from __future__ import annotations

from typing import Any

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
    ATTR_SUPPORTED,
    ATTR_UNHEALTHY,
    ATTR_UNHEALTHY_REASONS,
    ATTR_UNSUPPORTED,
    ATTR_UNSUPPORTED_REASONS,
    ATTR_UPDATE_KEY,
    ATTR_WS_EVENT,
    DOMAIN,
    EVENT_HEALTH_CHANGED,
    EVENT_SUPERVISOR_EVENT,
    EVENT_SUPERVISOR_UPDATE,
    EVENT_SUPPORTED_CHANGED,
    UPDATE_KEY_SUPERVISOR,
)
from .handler import HassIO

ISSUE_ID_UNHEALTHY = "unhealthy_system"
ISSUE_ID_UNSUPPORTED = "unsupported_system"

INFO_URL_UNHEALTHY = "https://www.home-assistant.io/more-info/unhealthy"
INFO_URL_UNSUPPORTED = "https://www.home-assistant.io/more-info/unsupported"

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


class SupervisorRepairs:
    """Create repairs from supervisor events."""

    def __init__(self, hass: HomeAssistant, client: HassIO) -> None:
        """Initialize supervisor repairs."""
        self._hass = hass
        self._client = client
        self._unsupported_reasons: set[str] = set()
        self._unhealthy_reasons: set[str] = set()

    @property
    def unhealthy_reasons(self) -> set[str]:
        """Get unhealthy reasons. Returns empty set if system is healthy."""
        return self._unhealthy_reasons

    @unhealthy_reasons.setter
    def unhealthy_reasons(self, reasons: set[str]) -> None:
        """Set unhealthy reasons. Create or delete repairs as necessary."""
        for unhealthy in reasons - self.unhealthy_reasons:
            if unhealthy in UNHEALTHY_REASONS:
                translation_key = f"unhealthy_{unhealthy}"
                translation_placeholders = None
            else:
                translation_key = "unhealthy"
                translation_placeholders = {"reason": unhealthy}

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
                translation_key = f"unsupported_{unsupported}"
                translation_placeholders = None
            else:
                translation_key = "unsupported"
                translation_placeholders = {"reason": unsupported}

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

    async def setup(self) -> None:
        """Create supervisor events listener."""
        await self.update()

        async_dispatcher_connect(
            self._hass, EVENT_SUPERVISOR_EVENT, self._supervisor_events_to_repairs
        )

    async def update(self) -> None:
        """Update repairs from Supervisor resolution center."""
        data = await self._client.get_resolution_info()
        self.unhealthy_reasons = set(data[ATTR_UNHEALTHY])
        self.unsupported_reasons = set(data[ATTR_UNSUPPORTED])

    @callback
    def _supervisor_events_to_repairs(self, event: dict[str, Any]) -> None:
        """Create repairs from supervisor events."""
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
