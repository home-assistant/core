"""The roomba component."""

import asyncio
import contextlib
import logging
from typing import Any

from roombapy import (
    RoombaClient,
    RoombaConnectionError,
    TransportOptions,
    generate_tls_context,
)

from homeassistant import exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant

from .connection import RoombaConnection
from .const import (
    CONF_BLID,
    CONF_CONTINUOUS,
    DEFAULT_CONTINUOUS,
    DOMAIN,
    PLATFORMS,
    ROOMBA_SESSION,
)
from .models import RoombaConfigEntry, RoombaData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: RoombaConfigEntry
) -> None:
    """Set the config entry up."""
    roomba = await async_create_roomba(
        hass,
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_BLID],
        config_entry.data[CONF_PASSWORD],
    )

    try:
        if not await async_connect_or_timeout(hass, roomba):
            raise exceptions.ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": config_entry.data[CONF_HOST]},
            )
    except CannotConnect as err:
        raise exceptions.ConfigEntryNotReady from err

    connection = RoombaConnection(
        hass,
        roomba,
        continuous=config_entry.options.get(CONF_CONTINUOUS, DEFAULT_CONTINUOUS),
        polling=not config_entry.pref_disable_polling,
        connect=async_connect_or_timeout,
        disconnect=async_disconnect_or_timeout,
    )

    async def _async_disconnect_roomba(event):
        await connection.async_stop()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect_roomba)
    )
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_options)
    )

    config_entry.runtime_data = RoombaData(
        roomba, config_entry.data[CONF_BLID], connection
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    connection.async_start()


async def _async_update_options(
    hass: HomeAssistant, config_entry: RoombaConfigEntry
) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_create_roomba(
    hass: HomeAssistant, host: str, blid: str, password: str
) -> RoombaClient:
    """Create a client without loading the TLS trust store in the event loop."""
    tls_context = await hass.async_add_executor_job(generate_tls_context)
    return RoombaClient(
        host, blid, password, transport=TransportOptions(tls_context=tls_context)
    )


async def async_connect_or_timeout(
    hass: HomeAssistant, roomba: RoombaClient
) -> dict[str, Any]:
    """Connect to vacuum."""
    try:
        name = None
        async with asyncio.timeout(10):
            _LOGGER.debug("Initialize connection to vacuum")
            await roomba.connect()
            while not roomba.connected or not roomba_reported_state(roomba):
                await asyncio.sleep(1)
            # Some models (such as Roomba 980) omit the 'name' field in initial telemetry
            name = roomba_reported_state(roomba).get("name") or "Roomba"
    except RoombaConnectionError as err:
        _LOGGER.debug("Error to connect to vacuum: %s", err)
        raise CannotConnect from err
    except TimeoutError as err:
        await async_disconnect_or_timeout(hass, roomba)
        _LOGGER.debug("Timeout expired: %s", err)
        raise CannotConnect from err

    return {ROOMBA_SESSION: roomba, CONF_NAME: name}


async def async_disconnect_or_timeout(
    hass: HomeAssistant, roomba: RoombaClient
) -> None:
    """Disconnect to vacuum."""
    _LOGGER.debug("Disconnect vacuum")
    with contextlib.suppress(TimeoutError):
        async with asyncio.timeout(3):
            await roomba.disconnect()


async def async_unload_entry(
    hass: HomeAssistant, config_entry: RoombaConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
    await config_entry.runtime_data.connection.async_stop()


def roomba_reported_state(roomba: RoombaClient) -> dict[str, Any]:
    """Roomba report."""
    return roomba.master_state.get("state", {}).get("reported", {})


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
