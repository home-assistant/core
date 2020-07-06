"""The dsmr component."""
import asyncio
from asyncio import CancelledError
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DSMR_VERSION,
    CONF_PRECISION,
    CONF_RECONNECT_INTERVAL,
    DEFAULT_DSMR_VERSION,
    DEFAULT_PORT,
    DEFAULT_PRECISION,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_DSMR_VERSION, default=DEFAULT_DSMR_VERSION): vol.All(
                    cv.string, vol.In(["5B", "5", "4", "2.2"])
                ),
                vol.Optional(CONF_RECONNECT_INTERVAL, default=30): int,
                vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): vol.Coerce(
                    int
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config: dict):
    """Set up the DSMR platform."""
    hass.data[DOMAIN] = {}

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up DSMR from a config entry."""
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    task = hass.data[DOMAIN][entry.title]

    task.cancel()
    try:
        await task
    except CancelledError:
        pass

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    return unload_ok
