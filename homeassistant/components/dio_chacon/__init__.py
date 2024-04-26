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
from homeassistant.core import Event, HomeAssistant, ServiceCall

from .const import (
    DOMAIN,
    EVENT_DIO_CHACON_DEVICE_STATE_CHANGED,
    EVENT_DIO_CHACON_DEVICE_STATE_RELOAD,
)

SERVICE_RELOAD_STATE = "reload_state"

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SWITCH]


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
    hass.data[DOMAIN][entry.entry_id] = dio_chacon_client

    # Disconnects the permanent websocket connection of home assistant shutdown
    async def call_disconnect(event: Event) -> None:
        await dio_chacon_client.disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, call_disconnect)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await hass.async_add_executor_job(setup_dio_chacon_service, hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    _LOGGER.debug("Start of async_unload_entry for dio_chacon integration")

    hass.services.async_remove(DOMAIN, SERVICE_RELOAD_STATE)

    dio_chacon_client = hass.data[DOMAIN][entry.entry_id]
    await dio_chacon_client.disconnect()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def setup_dio_chacon_service(hass: HomeAssistant) -> None:
    """Implement a custom service.

    This service allows user to reload all devices from the server.
    """

    def reload_devices_states(call: ServiceCall) -> None:
        """Trigger a reload of the states of the devices."""
        # No data input to call the service

        _LOGGER.debug("Call to the reload service for all dio chacon devices")
        hass.bus.fire(EVENT_DIO_CHACON_DEVICE_STATE_RELOAD)

    hass.services.register(DOMAIN, SERVICE_RELOAD_STATE, reload_devices_states)
