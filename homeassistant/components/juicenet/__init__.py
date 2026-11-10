"""The JuiceNet integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up JuiceNet from a config entry."""

    ir.async_create_issue(
        hass,
        DOMAIN,
        DOMAIN,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="integration_removed",
        translation_placeholders={
            "entries": "/config/integrations/integration/juicenet",
        },
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        ir.async_delete_issue(hass, DOMAIN, DOMAIN)
