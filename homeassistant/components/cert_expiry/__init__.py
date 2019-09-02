"""The cert_expiry component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType


async def async_setup(hass, config):
    """Platform setup, do nothing."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Load the saved entities."""

    @callback
    def async_start(_):
        """Load the entry after the start event."""
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "sensor")
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, async_start)

    return True
