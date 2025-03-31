"""The Sun WEG inverter sensor integration."""

from homeassistant.config_entries import ConfigEntry
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
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        ir.async_delete_issue(hass, DOMAIN, DOMAIN)
        # Remove any remaining disabled or ignored entries
        for _entry in hass.config_entries.async_entries(DOMAIN):
            hass.async_create_task(hass.config_entries.async_remove(_entry.entry_id))
