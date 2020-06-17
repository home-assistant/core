"""The Logitech Squeezebox integration."""

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant

from .media_player import start_server_discovery


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Logitech Squeezebox component."""
    if hass.is_running:
        await start_server_discovery(hass)
    else:
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, start_server_discovery(hass)
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Logitech Squeezebox from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN)
    )
    return True
