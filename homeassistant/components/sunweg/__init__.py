"""The Sun WEG inverter sensor integration."""

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

DOMAIN = "sunweg"


async def async_setup_entry(hass: HomeAssistant, _: ConfigEntry) -> bool:
    """Load the saved entities."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        DOMAIN,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="integration_removed",
        translation_placeholders={
            "issue": "https://github.com/rokam/sunweg/issues/13",
            "entries": "/config/integrations/integration/sunweg",
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
