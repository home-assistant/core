"""The Remootio integration."""
from __future__ import annotations

import logging

from aioremootio import ConnectionOptions, RemootioClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME, CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback

from .const import (
    ATTR_SERIAL_NUMBER,
    ATTR_TYPE,
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    CONF_SERIAL_NUMBER,
    DOMAIN,
    EVENT_HANDLER_CALLBACK,
    EVENT_TYPE,
    REMOOTIO_CLIENT,
)
from .cover import RemootioCoverEvent
from .utils import create_client

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Remootio from a config entry."""

    _LOGGER.debug("Doing async_setup_entry. entry [%s]", entry.as_dict())

    @callback
    def handle_event(event: RemootioCoverEvent) -> None:
        _LOGGER.debug(
            "Firing event. EvenType [%s] RemootioCoverEntityId [%s] RemootioDeviceSerialNumber [%s]",
            event.type,
            event.entity_id,
            event.device_serial_number,
        )

        hass.bus.async_fire(
            EVENT_TYPE,
            {
                ATTR_ENTITY_ID: event.entity_id,
                ATTR_SERIAL_NUMBER: event.device_serial_number,
                ATTR_NAME: event.entity_name,
                ATTR_TYPE: event.type,
            },
        )

    connection_options: ConnectionOptions = ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data[CONF_API_SECRET_KEY],
        entry.data[CONF_API_AUTH_KEY],
        False,
    )
    serial_number: str = entry.data[CONF_SERIAL_NUMBER]

    remootio_client: RemootioClient = await create_client(
        hass, connection_options, _LOGGER, serial_number
    )

    async def terminate_client() -> None:
        _LOGGER.debug(
            "Remootio client will now be terminated. entry [%s]", entry.as_dict()
        )

        terminated: bool = await remootio_client.terminate()
        if terminated:
            _LOGGER.debug(
                "Remootio client successfully terminated. entry [%s]", entry.as_dict()
            )

    entry.async_on_unload(terminate_client)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        REMOOTIO_CLIENT: remootio_client,
        EVENT_HANDLER_CALLBACK: handle_event,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    _LOGGER.debug(
        "Doing async_unload_entry. entry [%s] hass.data[%s][%s] [%s]",
        entry.as_dict(),
        DOMAIN,
        entry.entry_id,
        hass.data.get(DOMAIN, {}).get(entry.entry_id, {}),
    )

    platforms_unloaded = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    return platforms_unloaded
