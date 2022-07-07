"""The resolution center integration."""
from __future__ import annotations

import dataclasses

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .issue_registry import async_get as async_get_issue_registry
from .models import Issue, IssueSeverity


@callback
def async_create_issue(
    hass: HomeAssistant,
    domain: str,
    issue_id: str,
    *,
    breaks_in_ha_version: str | None = None,
    is_fixable: bool,
    learn_more_url: str | None = None,
    severity: IssueSeverity,
    translation_key: str,
    translation_placeholders: dict[str, str] | None,
) -> None:
    """Create an issue, or replace an existing one."""
    # Verify the breaks_in_ha_version is a valid version string
    if breaks_in_ha_version:
        AwesomeVersion(
            breaks_in_ha_version,
            ensure_strategy=AwesomeVersionStrategy.CALVER,
            find_first_match=True,
        )

    issue_registry = async_get_issue_registry(hass)

    issue_entry = issue_registry.async_get_or_create(domain, issue_id)

    issue = Issue(
        breaks_in_ha_version=breaks_in_ha_version,
        domain=domain,
        issue_id=issue_id,
        dismissed=issue_entry.is_dismissed,
        dismissed_version=issue_entry.dismissed_version,
        is_fixable=is_fixable,
        learn_more_url=learn_more_url,
        severity=severity,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
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
        dismissed_version=issue_entry.dismissed_version,
    )
    hass.data[DOMAIN]["issues"][(domain, issue_id)] = issue
