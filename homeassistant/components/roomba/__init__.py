"""The roomba component."""

import asyncio
import contextlib
from functools import partial
import logging
from typing import Any

from roombapy import Roomba, RoombaConnectionError, RoombaFactory

from homeassistant import exceptions
from homeassistant.const import (
    CONF_DELAY,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant

from .const import CONF_BLID, CONF_CONN_MODE, CONF_CONTINUOUS, PLATFORMS, ROOMBA_SESSION
from .models import RoombaConfigEntry, RoombaData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: RoombaConfigEntry
) -> bool:
    """Set the config entry up."""
    # Set up roomba platforms with config entry

    if not config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            options={
                CONF_CONN_MODE: config_entry.data[CONF_CONN_MODE],
                CONF_DELAY: config_entry.data[CONF_DELAY],
            },
        )

    roomba = await hass.async_add_executor_job(
        partial(
            RoombaFactory.create_roomba,
            address=config_entry.data[CONF_HOST],
            blid=config_entry.data[CONF_BLID],
            password=config_entry.data[CONF_PASSWORD],
            mode=config_entry.options[CONF_CONN_MODE],
            delay=config_entry.options[CONF_DELAY],
        )
    )

    try:
        if not await async_connect_or_timeout(hass, roomba):
            return False
    except CannotConnect as err:
        raise exceptions.ConfigEntryNotReady from err

    async def _async_disconnect_roomba(event):
        await async_disconnect_or_timeout(hass, roomba)

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect_roomba)
    )

    config_entry.runtime_data = RoombaData(roomba, config_entry.data[CONF_BLID])

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    if not config_entry.update_listeners:
        config_entry.add_update_listener(async_update_options)

    return True


async def async_connect_or_timeout(
    hass: HomeAssistant, roomba: Roomba
) -> dict[str, Any]:
    """Connect to vacuum."""
    try:
        name = None
        async with asyncio.timeout(10):
            _LOGGER.debug("Initialize connection to vacuum")
            await hass.async_add_executor_job(roomba.connect)
            while not roomba.roomba_connected or name is None:
                # Waiting for connection and check data is ready
                name = roomba_reported_state(roomba).get("name", None)
                if name:
                    break
                await asyncio.sleep(1)
    except RoombaConnectionError as err:
        _LOGGER.debug("Error to connect to vacuum: %s", err)
        raise CannotConnect from err
    except TimeoutError as err:
        # api looping if user or password incorrect and roomba exist
        await async_disconnect_or_timeout(hass, roomba)
        _LOGGER.debug("Timeout expired: %s", err)
        raise CannotConnect from err

    return {ROOMBA_SESSION: roomba, CONF_NAME: name}


async def async_disconnect_or_timeout(hass: HomeAssistant, roomba: Roomba) -> None:
    """Disconnect to vacuum."""
    _LOGGER.debug("Disconnect vacuum")
    with contextlib.suppress(TimeoutError):
        async with asyncio.timeout(3):
            await hass.async_add_executor_job(roomba.disconnect)


async def async_update_options(
    hass: HomeAssistant, config_entry: RoombaConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: RoombaConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        await async_disconnect_or_timeout(hass, roomba=config_entry.runtime_data.roomba)

    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: RoombaConfigEntry
) -> bool:
    """Migrate Roomba config entry."""
    _LOGGER.debug(
        "Roomba configuration migration from version %s",
        config_entry.version,
    )

    if config_entry.version < 2:
        old_options = config_entry.options or config_entry.data
        new_conn_mode = (
            "continuous" if old_options[CONF_CONTINUOUS] is True else "periodic"
        )
        new_options = {
            CONF_CONN_MODE: new_conn_mode,
            CONF_DELAY: old_options[CONF_DELAY],
        }

        hass.config_entries.async_update_entry(
            config_entry, options=new_options, version=2
        )

        _LOGGER.debug("Roomba configuration was migrated to version %s successfully", 2)

    return True


def roomba_reported_state(roomba: Roomba) -> dict[str, Any]:
    """Roomba report."""
    return roomba.master_state.get("state", {}).get("reported", {})


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
