"""Support for SmartHab device integration."""
import asyncio
import logging

import pysmarthab
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

DOMAIN = "smarthab"
DATA_HUB = "hub"
COMPONENTS = ["light", "cover"]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config) -> bool:
    """Set up the SmartHab platform."""

    hass.data.setdefault(DOMAIN, {})
    sh_conf = config.get(DOMAIN)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=sh_conf,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up config entry for SmartHab integration."""

    # Assign configuration variables
    username = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    # Setup connection with SmartHab API
    hub = pysmarthab.SmartHab()

    try:
        await hub.async_login(username, password)
    except pysmarthab.RequestFailedException:
        _LOGGER.exception("Error while trying to reach SmartHab API")
        raise ConfigEntryNotReady

    # Pass hub object to child platforms
    hass.data[DOMAIN][entry.entry_id] = {DATA_HUB: hub}

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload config entry from SmartHab integration."""

    result = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in COMPONENTS
            ]
        )
    )

    if result:
        hass.data[DOMAIN].pop(entry.entry_id)

    return result
