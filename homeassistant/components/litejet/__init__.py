"""Support for the LiteJet lighting system."""
import asyncio
import logging

import pylitejet
from serial import SerialException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from .const import CONF_EXCLUDE_NAMES, CONF_INCLUDE_SWITCHES, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_PORT): cv.string,
                    vol.Optional(CONF_EXCLUDE_NAMES): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(CONF_INCLUDE_SWITCHES, default=False): cv.boolean,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the LiteJet component."""
    if DOMAIN in config and not hass.config_entries.async_entries(DOMAIN):
        # No config entry exists and configuration.yaml config exists, trigger the import flow.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LiteJet via a config entry."""
    port = entry.data[CONF_PORT]

    try:
        system = pylitejet.LiteJet(port)
    except SerialException as ex:
        _LOGGER.error("Error connecting to the LiteJet MCP at %s", port, exc_info=ex)
        raise ConfigEntryNotReady from ex

    hass.data[DOMAIN] = system

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a LiteJet config entry."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].close()
        hass.data.pop(DOMAIN)

    return unload_ok
