"""The dio_chacon integration."""
import logging
from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, EVENT_DIO_CHACON_DEVICE_STATE_CHANGED

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up dio_chacon from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    config = entry.data

    def callback_device_state(data: Any) -> None:
        """Receive callback for device state notification pushed from the server."""

        hass.bus.fire(EVENT_DIO_CHACON_DEVICE_STATE_CHANGED, data)

    # Authentication verification and login
    dio_chacon_client = DIOChaconAPIClient(
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        config[CONF_UNIQUE_ID],
        callback_device_state,
    )

    # Store an API object for the platforms to access
    hass.data[DOMAIN][entry.entry_id] = dio_chacon_client

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, dio_chacon_client.disconnect())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    dio_chacon_client = hass.data[DOMAIN][entry.entry_id]

    dio_chacon_client.disconnect()

    return unload_ok
