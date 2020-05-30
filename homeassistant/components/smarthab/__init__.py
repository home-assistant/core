"""Support for SmartHab device integration."""
import logging

import pysmarthab
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

DOMAIN = "smarthab"
DATA_HUB = "hub"

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
    username = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)

    # Setup connection with SmartHab API
    hub = pysmarthab.SmartHab()

    try:
        await hass.async_add_executor_job(hub.login, username, password)
    except pysmarthab.RequestFailedException as ex:
        _LOGGER.error("Error while trying to reach SmartHab API.")
        _LOGGER.debug(ex, exc_info=True)
        return False

    # Pass hub object to child platforms
    hass.data[DOMAIN][entry.entry_id] = {DATA_HUB: hub}

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "light")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "cover")
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload config entry from SmartHab integration."""
    await hass.config_entries.async_forward_entry_unload(entry, "light")
    await hass.config_entries.async_forward_entry_unload(entry, "cover")
