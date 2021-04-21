"""The epson integration."""
import asyncio
import logging

from epson_projector import Projector
from epson_projector.const import (
    PWR_OFF_STATE,
    STATE_UNAVAILABLE as EPSON_STATE_UNAVAILABLE,
)

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_registry import (
    async_get_registry,
    async_migrate_entries,
)

from .const import DOMAIN, HTTP
from .exceptions import CannotConnect, PoweredOff

PLATFORMS = [MEDIA_PLAYER_PLATFORM]

_LOGGER = logging.getLogger(__name__)


async def validate_projector(
    hass: HomeAssistant, host, check_power=True, check_powered_on=True
):
    """Validate the given projector host allows us to connect."""
    epson_proj = Projector(
        host=host,
        websession=async_get_clientsession(hass, verify_ssl=False),
        type=HTTP,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up epson from a config entry."""
    try:
        projector = await validate_projector(
            hass=hass,
            host=entry.data[CONF_HOST],
            check_power=False,
            check_powered_on=False,
        )
    except CannotConnect:
        _LOGGER.warning("Cannot connect to projector %s", entry.data[CONF_HOST])
        return False
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = projector
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_migrate_entry(hass, config_entry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating unique_id in %s", config_entry.version)

    async def get_unique_id():
        try:
            projector = await validate_projector(hass, config_entry.data[CONF_HOST])
        except (CannotConnect, PoweredOff):
            return None
        else:
            return await projector.get_serial_number()

    if config_entry.version == 1:
        data = {CONF_HOST: config_entry.data[CONF_HOST]}
        hass.config_entries.async_update_entry(config_entry, data=data)
        config_entry.version = 2
    if config_entry.version == 2:
        old_unique_id = config_entry.unique_id
        new_unique_id = await get_unique_id()
        registry = await async_get_registry(hass)
        old_entity_id = registry.async_get_entity_id(
            "media_player", DOMAIN, config_entry.entry_id
        )
        if old_entity_id is not None:
            registry.async_remove(old_entity_id)

        @callback
        def update_unique_id(entity_entry):
            """Update unique ID of entity entry."""
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old_unique_id, new_unique_id
                )
            }

        if new_unique_id and old_unique_id != new_unique_id:
            await async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

            hass.config_entries.async_update_entry(
                config_entry, unique_id=new_unique_id
            )

    return True
