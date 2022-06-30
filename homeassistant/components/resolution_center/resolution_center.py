"""The resolution center integration."""
from __future__ import annotations

import dataclasses

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)

from .const import DOMAIN
from .issue_registry import async_get as async_get_issue_registry
from .models import Issue, ResolutionCenterProtocol


async def async_process_resolution_center_platforms(hass: HomeAssistant):
    """Start processing resolution center platforms."""
    hass.data[DOMAIN]["resolution_center_platforms"] = {}

    await async_process_integration_platforms(
        hass, DOMAIN, _register_resolution_center_platform
    )

    return True


async def _register_resolution_center_platform(
    hass: HomeAssistant, integration_domain: str, platform: ResolutionCenterProtocol
):
    """Register a resolution center platform."""
    if integration_domain == DOMAIN:
        return
    if not hasattr(platform, "async_fix_issue"):
        raise HomeAssistantError(f"Invalid resolution center platform {platform}")
    hass.data[DOMAIN]["resolution_center_platforms"][integration_domain] = platform


@callback
def async_create_issue(
    hass: HomeAssistant,
    domain: str,
    issue_id: str,
    *,
    breaks_in_ha_version: str | None = None,
    description_i18n_key: str | None = None,
    fix_label_i18n_key: str | None = None,
    is_fixable: bool,
    learn_more_url: str | None = None,
    placeholders_i18n_keys: dict[str, str] | None = None,
    severity: str,
    title_i18n_key: str,
) -> None:
    """Create an issue, or replace an existing one."""
    issue_registry = async_get_issue_registry(hass)

    issue_entry = issue_registry.async_get_or_create(domain, issue_id)

    issue = Issue(
        breaks_in_ha_version=breaks_in_ha_version,
        description_i18n_key=description_i18n_key,
        domain=domain,
        issue_id=issue_id,
        dismissed=issue_entry.is_dismissed,
        dismissed_version_major=issue_entry.dismissed_version_major,
        dismissed_version_minor=issue_entry.dismissed_version_minor,
        dismissed_version_patch=issue_entry.dismissed_version_patch,
        fix_label_i18n_key=fix_label_i18n_key,
        is_fixable=is_fixable,
        learn_more_url=learn_more_url,
        placeholders_i18n_keys=placeholders_i18n_keys,
        severity=severity,
        title_i18n_key=title_i18n_key,
    )
    hass.data[DOMAIN]["issues"][(domain, issue_id)] = issue


@callback
def async_delete_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Delete an issue.

    It is not an error to delete an issue that does not exist.
    """
    if hass.data[DOMAIN]["issues"].pop((domain, issue_id), None) is None:
        return

    issue_registry = async_get_issue_registry(hass)
    issue_registry.async_delete(domain, issue_id)


@callback
def async_dismiss_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Dismiss an issue.

    Will raise if the issue does not exist.
    """
    issue_registry = async_get_issue_registry(hass)

    issue: Issue = hass.data[DOMAIN]["issues"][(domain, issue_id)]

    issue_entry = issue_registry.async_dismiss(domain, issue_id)

    issue = dataclasses.replace(
        issue,
        dismissed=issue_entry.is_dismissed,
        dismissed_version_major=issue_entry.dismissed_version_major,
        dismissed_version_minor=issue_entry.dismissed_version_minor,
        dismissed_version_patch=issue_entry.dismissed_version_patch,
    )
    hass.data[DOMAIN]["issues"][(domain, issue_id)] = issue


async def async_fix_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Fix an issue."""

    if "resolution_center_platforms" not in hass.data[DOMAIN]:
        await async_process_resolution_center_platforms(hass)

    hardware_platforms: dict[str, ResolutionCenterProtocol] = hass.data[DOMAIN][
        "resolution_center_platforms"
    ]
    platform = hardware_platforms[domain]
    if await platform.async_fix_issue(hass, issue_id):
        issue_registry = async_get_issue_registry(hass)
        issue_registry.async_delete(domain, issue_id)
        async_delete_issue(hass, domain, issue_id)
