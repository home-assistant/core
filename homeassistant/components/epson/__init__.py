"""Epson integration."""
import asyncio
import logging

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import load_platform

from .const import (  # noqa: F401; pylint:disable=unused-import
    CONF_PROJECTORS,
    CONFIG_SCHEMA,
    EPSON_DOMAIN as DOMAIN,
    PLATFORMS as SUPPORTED_PLATFORMS,
    PROTO_HTTP,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Epson component."""
    hass.data.setdefault(DOMAIN, {})

    # Load platforms
    if config.get(DOMAIN) is not None:
        for component, conf_key in ((MEDIA_PLAYER_PLATFORM, CONF_PROJECTORS),):
            if conf_key in config[DOMAIN]:
                load_platform(hass, component, DOMAIN, config[DOMAIN][conf_key], config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Epson entity from a config entry."""
    for component in SUPPORTED_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in SUPPORTED_PLATFORMS
            ]
        )
    )
    return unload_ok


async def async_migrate_entry(_, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.data, CONF_PROTOCOL: PROTO_HTTP}
        config_entry.data = {**new}
        config_entry.version = 2

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
