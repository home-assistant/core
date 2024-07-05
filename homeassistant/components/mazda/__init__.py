"""The Mazda Connected Services integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

DOMAIN = "mazda"


async def async_setup_entry(hass: HomeAssistant, _: ConfigEntry) -> bool:
    """Set up Mazda Connected Services from a config entry."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        DOMAIN,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="integration_removed",
        translation_placeholders={
            "dmca": "https://github.com/github/dmca/blob/master/2023/10/2023-10-10-mazda.md",
            "entries": "/config/integrations/integration/mazda",
        },
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if all(
        config_entry.state is ConfigEntryState.NOT_LOADED
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.entry_id != entry.entry_id
    ):
        ir.async_delete_issue(hass, DOMAIN, DOMAIN)

    return True
