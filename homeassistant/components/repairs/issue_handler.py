"""The repairs integration."""
from __future__ import annotations

import functools as ft
from typing import Any

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.util.async_ import run_callback_threadsafe

from .const import DOMAIN
from .issue_registry import async_get as async_get_issue_registry
from .models import IssueSeverity, RepairsFlow, RepairsProtocol


class RepairsFlowManager(data_entry_flow.FlowManager):
    """Manage repairs flows."""

    async def async_create_flow(
        self,
        handler_key: Any,
        *,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> RepairsFlow:
        """Create a flow. platform is a repairs module."""
        if "platforms" not in self.hass.data[DOMAIN]:
            await async_process_repairs_platforms(self.hass)

        platforms: dict[str, RepairsProtocol] = self.hass.data[DOMAIN]["platforms"]
        if handler_key not in platforms:
            raise data_entry_flow.UnknownHandler
        platform = platforms[handler_key]

        assert data and "issue_id" in data
        issue_id = data["issue_id"]

        issue_registry = async_get_issue_registry(self.hass)
        issue = issue_registry.async_get_issue(handler_key, issue_id)
        if issue is None or not issue.is_fixable:
            raise data_entry_flow.UnknownStep

        return await platform.async_create_fix_flow(self.hass, issue_id)

    async def async_finish_flow(
        self, flow: data_entry_flow.FlowHandler, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Complete a fix flow."""
        async_delete_issue(self.hass, flow.handler, flow.init_data["issue_id"])
        if "result" not in result:
            result["result"] = None
        return result


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Initialize repairs."""
    hass.data[DOMAIN]["flow_manager"] = RepairsFlowManager(hass)


async def async_process_repairs_platforms(hass: HomeAssistant) -> None:
    """Start processing repairs platforms."""
    hass.data[DOMAIN]["platforms"] = {}

    await async_process_integration_platforms(hass, DOMAIN, _register_repairs_platform)


async def _register_repairs_platform(
    hass: HomeAssistant, integration_domain: str, platform: RepairsProtocol
) -> None:
    """Register a repairs platform."""
    if not hasattr(platform, "async_create_fix_flow"):
        raise HomeAssistantError(f"Invalid repairs platform {platform}")
    hass.data[DOMAIN]["platforms"][integration_domain] = platform


@callback
def async_create_issue(
    hass: HomeAssistant,
    domain: str,
    issue_id: str,
    *,
    issue_domain: str | None = None,
    breaks_in_ha_version: str | None = None,
    is_fixable: bool,
    learn_more_url: str | None = None,
    severity: IssueSeverity,
    translation_key: str,
    translation_placeholders: dict[str, str] | None = None,
) -> None:
    """Create an issue, or replace an existing one."""
    # Verify the breaks_in_ha_version is a valid version string
    if breaks_in_ha_version:
        AwesomeVersion(
            breaks_in_ha_version,
            ensure_strategy=AwesomeVersionStrategy.CALVER,
            find_first_match=False,
        )

    issue_registry = async_get_issue_registry(hass)
    issue_registry.async_get_or_create(
        domain,
        issue_id,
        issue_domain=issue_domain,
        breaks_in_ha_version=breaks_in_ha_version,
        is_fixable=is_fixable,
        learn_more_url=learn_more_url,
        severity=severity,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
    )


def create_issue(
    hass: HomeAssistant,
    domain: str,
    issue_id: str,
    *,
    breaks_in_ha_version: str | None = None,
    is_fixable: bool,
    learn_more_url: str | None = None,
    severity: IssueSeverity,
    translation_key: str,
    translation_placeholders: dict[str, str] | None = None,
) -> None:
    """Create an issue, or replace an existing one."""
    return run_callback_threadsafe(
        hass.loop,
        ft.partial(
            async_create_issue,
            hass,
            domain,
            issue_id,
            breaks_in_ha_version=breaks_in_ha_version,
            is_fixable=is_fixable,
            learn_more_url=learn_more_url,
            severity=severity,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        ),
    ).result()


@callback
def async_delete_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Delete an issue.

    It is not an error to delete an issue that does not exist.
    """
    issue_registry = async_get_issue_registry(hass)
    issue_registry.async_delete(domain, issue_id)


def delete_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Delete an issue.

    It is not an error to delete an issue that does not exist.
    """
    return run_callback_threadsafe(
        hass.loop, async_delete_issue, hass, domain, issue_id
    ).result()


@callback
def async_ignore_issue(
    hass: HomeAssistant, domain: str, issue_id: str, ignore: bool
) -> None:
    """Ignore an issue.

    Will raise if the issue does not exist.
    """
    issue_registry = async_get_issue_registry(hass)
    issue_registry.async_ignore(domain, issue_id, ignore)
