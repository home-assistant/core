"""The roomba component."""
import asyncio
import logging

import async_timeout
from roomba import Roomba, RoombaConnectionError

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import COMPONENTS, CONF_CERT, CONF_CONTINUOUS, CONF_DELAY, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the roomba environment."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
            )
        )


async def async_setup_entry(hass, config_entry):
    """Set the config entry up."""
    # Set up roomba platforms with config entry
    _LOGGER.debug(config_entry.entry_id)
    if config_entry.data is None:
        return False

    if not config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            options={
                "continuous": config_entry.data[CONF_CONTINUOUS],
                "delay": config_entry.data[CONF_DELAY],
            },
        )

    if "roomba" not in hass.data[DOMAIN]:
        roomba = Roomba(
            address=config_entry.data[CONF_HOST],
            blid=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            cert_name=config_entry.data[CONF_CERT],
            continuous=config_entry.options[CONF_CONTINUOUS],
            delay=config_entry.options[CONF_DELAY],
        )

        try:
            if not await async_connect_or_timeout(hass, roomba):
                return False
        except CannotConnect:
            raise exceptions.ConfigEntryNotReady

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    config_entry.add_update_listener(async_update_options)

    return True


async def async_connect_or_timeout(hass, roomba):
    """Connect to vacuum."""
    try:
        hass.data[DOMAIN]["name"] = name = None
        with async_timeout.timeout(10):
            await hass.async_add_job(roomba.connect)
            _LOGGER.debug("Initialize to connect to vacuum")
            while not roomba.roomba_connected or name is None:
                # Waiting for connection and check datas ready
                name = roomba_reported_state(roomba).get("name", None)
                hass.data[DOMAIN]["roomba"] = roomba
                hass.data[DOMAIN]["name"] = name
                await asyncio.sleep(1)
    except RoombaConnectionError:
        _LOGGER.error("Error to connect to vacuum")
        raise CannotConnect
    except asyncio.TimeoutError:
        # api looping if user or password incorrect and roomba exist
        await async_disconnect_or_timeout(hass, roomba)
        _LOGGER.exception("Timeout expired")
        raise CannotConnect

    return True


async def async_disconnect_or_timeout(hass, roomba):
    """Disconnect to vacuum."""
    with async_timeout.timeout(3):
        await hass.async_add_job(roomba.disconnect)
        hass.data[DOMAIN].pop("roomba", None)
    await asyncio.sleep(1)
    return True


async def async_update_options(hass, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    _LOGGER.debug("Unload Entries")
    await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_unload(config_entry, component)
            for component in COMPONENTS
        ]
    )
    return await async_disconnect_or_timeout(hass, roomba=hass.data[DOMAIN]["roomba"])


def roomba_reported_state(roomba):
    """Roomba report."""
    return roomba.master_state.get("state", {}).get("reported", {})


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
