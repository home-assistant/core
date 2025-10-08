"""The Volvo On Call integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Volvo On Call integration."""

    # Create repair issue pointing to the new volvo integration
    ir.async_create_issue(
        hass,
        DOMAIN,
        "volvooncall_deprecated",
        breaks_in_ha_version="2026.3",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="volvooncall_deprecated",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Only delete the repair issue if this is the last config entry for this domain
    remaining_entries = [
        config_entry
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.entry_id != entry.entry_id
    ]

    if not remaining_entries:
        ir.async_delete_issue(
            hass,
            DOMAIN,
            "volvooncall_deprecated",
        )

    return True
