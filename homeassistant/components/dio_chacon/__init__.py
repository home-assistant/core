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
from homeassistant.core import Event, HomeAssistant

from .const import DOMAIN, EVENT_DIO_CHACON_DEVICE_STATE_CHANGED

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up dio_chacon from a config entry."""

    _LOGGER.debug("Start of async_setup_entry for dio_chacon integration")

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
    entry.runtime_data = dio_chacon_client

    # Disconnects the permanent websocket connection of home assistant on shutdown
    async def call_disconnect(event: Event) -> None:
        await dio_chacon_client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, call_disconnect)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    _LOGGER.debug("Start of async_unload_entry for dio_chacon integration")

    dio_chacon_client = entry.runtime_data

    await dio_chacon_client.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
