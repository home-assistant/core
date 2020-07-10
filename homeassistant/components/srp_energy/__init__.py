"""The SRP Energy integration."""
import asyncio
import logging
from srpenergy.client import SrpEnergyClient

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ID): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [DOMAIN]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the SRP Energy component."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True

    # name = config[DOMAIN][CONF_NAME]
    # username = config[DOMAIN][CONF_USERNAME]
    # password = config[DOMAIN][CONF_PASSWORD]
    # account_id = config[DOMAIN][CONF_ID]

    # try:
    #     srp_client = SrpEnergyClient(account_id, username, password)
    # except ValueError as err:
    #     _LOGGER.error("Couldn't connect to %s. %s", name, err)
    #     return False

    # if not srp_client.validate():
    #     _LOGGER.error("Couldn't connect to %s. Check credentials", name)
    #     return False

    # return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up SRP Energy from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    _LOGGER.error("Testing")
    for component in PLATFORMS:

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
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

