"""Repairs support for KNX."""

from __future__ import annotations

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


@callback
def migrate_notify_issue(hass: HomeAssistant) -> None:
    """Create issue for notify service deprecation."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "migrate_notify",
        breaks_in_ha_version="2024.11.0",
        issue_domain=Platform.NOTIFY.value,
        is_fixable=True,
        is_persistent=True,
        translation_key="migrate_notify",
        severity=ir.IssueSeverity.WARNING,
    )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    assert issue_id == "migrate_notify"
    return ConfirmRepairFlow()
