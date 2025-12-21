"""The epson integration."""

import logging

from epson_projector import Projector
from epson_projector.const import (
    PWR_OFF_STATE,
    STATE_UNAVAILABLE as EPSON_STATE_UNAVAILABLE,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CONNECTION_TYPE, HTTP
from .exceptions import CannotConnect, PoweredOff

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)

type EpsonConfigEntry = ConfigEntry[Projector]


async def validate_projector(
    hass: HomeAssistant,
    host: str,
    conn_type: str,
    check_power: bool = True,
    check_powered_on: bool = True,
):
    """Validate the given projector host allows us to connect."""
    epson_proj = Projector(
        host=host,
        websession=async_get_clientsession(hass, verify_ssl=False),
        type=conn_type,
    )
    if check_power:
        _power = await epson_proj.get_power()
        if not _power or _power == EPSON_STATE_UNAVAILABLE:
            _LOGGER.debug("Cannot connect to projector")
            raise CannotConnect
        if _power == PWR_OFF_STATE and check_powered_on:
            _LOGGER.debug("Projector is off")
            raise PoweredOff
    return epson_proj


async def async_setup_entry(hass: HomeAssistant, entry: EpsonConfigEntry) -> bool:
    """Set up epson from a config entry."""
    projector = await validate_projector(
        hass=hass,
        host=entry.data[CONF_HOST],
        conn_type=entry.data[CONF_CONNECTION_TYPE],
        check_power=False,
        check_powered_on=False,
    )
    entry.runtime_data = projector
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(projector.close)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EpsonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: EpsonConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1 or config_entry.minor_version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1 and config_entry.minor_version == 1:
        new_data = {**config_entry.data}
        new_data[CONF_CONNECTION_TYPE] = HTTP

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=1, minor_version=2
        )

    _LOGGER.debug(
        "Migration to configuration version %s successful", config_entry.version
    )

    return True
