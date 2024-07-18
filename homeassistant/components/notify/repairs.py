"""Repairs support for notify integration."""

from __future__ import annotations

from homeassistant.components.repairs import RepairsFlow
from homeassistant.components.repairs.issue_handler import ConfirmRepairFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


@callback
def migrate_notify_issue(
    hass: HomeAssistant,
    domain: str,
    integration_title: str,
    breaks_in_ha_version: str,
    service_name: str | None = None,
) -> None:
    """Ensure an issue is registered."""
    if service_name is not None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"migrate_notify_{domain}_{service_name}",
            breaks_in_ha_version=breaks_in_ha_version,
            issue_domain=domain,
            is_fixable=True,
            is_persistent=True,
            translation_key="migrate_notify_service",
            translation_placeholders={
                "domain": domain,
                "integration_title": integration_title,
                "service_name": service_name,
            },
            severity=ir.IssueSeverity.WARNING,
        )
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"migrate_notify_{domain}",
        breaks_in_ha_version=breaks_in_ha_version,
        issue_domain=domain,
        is_fixable=True,
        is_persistent=True,
        translation_key="migrate_notify",
        translation_placeholders={
            "domain": domain,
            "integration_title": integration_title,
        },
        severity=ir.IssueSeverity.WARNING,
    )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    assert issue_id.startswith("migrate_notify_")
    return ConfirmRepairFlow()
