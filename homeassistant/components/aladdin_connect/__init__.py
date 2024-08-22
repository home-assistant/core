"""The Aladdin Connect Genie integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.helpers import issue_registry as ir

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

DOMAIN = "aladdin_connect"


async def async_setup_entry(hass: HomeAssistant, _: ConfigEntry) -> bool:
    """Set up Aladdin Connect from a config entry."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        DOMAIN,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="integration_removed",
        translation_placeholders={
            "entries": "/config/integrations/integration/aladdin_connect",
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
