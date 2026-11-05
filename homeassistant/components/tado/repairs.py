"""Repair implementations."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_DEFAULT,
    DOMAIN,
    WATER_HEATER_FALLBACK_REPAIR,
)
from .coordinator import TadoConfigEntry


def manage_water_heater_fallback_issue(
    hass: HomeAssistant,
    entry: TadoConfigEntry,
    has_water_heaters: bool,
    integration_overlay_fallback: str | None,
) -> None:
    """Notify users about water heater respecting fallback setting."""
    # The fallback is an entry option shared by all hot water zones
    issue_id = f"{WATER_HEATER_FALLBACK_REPAIR}_{entry.entry_id}"
    if has_water_heaters and integration_overlay_fallback in (
        CONST_OVERLAY_TADO_DEFAULT,
        CONST_OVERLAY_MANUAL,
    ):
        ir.async_create_issue(
            hass=hass,
            domain=DOMAIN,
            issue_id=issue_id,
            config_entry_id=entry.entry_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=WATER_HEATER_FALLBACK_REPAIR,
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
