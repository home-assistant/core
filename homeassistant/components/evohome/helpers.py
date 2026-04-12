"""Helpers for the Evohome integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


@callback
def async_create_deprecation_issue_once(
    hass: HomeAssistant, issue_id: str, breaks_in_ha_version: str
) -> None:
    """Create a deprecation issue only if it does not already exist.

    Deprecated actions can be triggered repeatedly (for example by automations).
    This helper avoids repeated issue updates for the same issue_id.
    """

    issue_registry = ir.async_get(hass)
    if issue_registry.async_get_issue(DOMAIN, issue_id) is not None:
        return

    issue_registry.async_get_or_create(
        DOMAIN,
        issue_id,
        breaks_in_ha_version=breaks_in_ha_version,
        is_fixable=False,
        is_persistent=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=issue_id,
    )
