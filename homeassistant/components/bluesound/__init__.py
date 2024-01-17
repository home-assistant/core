"""The bluesound component."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_HOSTS, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_PORT, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOSTS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                }
            ],
        )
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bluesound component."""
    conf = config.get(DOMAIN)

    _LOGGER.debug("Bluesound async_setup: %r", conf)

    hass.data[DOMAIN] = []

    if conf is not None:
        if hosts := conf.get(CONF_HOSTS):
            for host in hosts:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": config_entries.SOURCE_IMPORT},
                        data=host,
                    )
                )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bluesound from a config entry."""
    _LOGGER.debug("Bluesound async_setup_entry: %s: %r", entry.entry_id, entry.data)

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Bluesound config entry."""
    _LOGGER.debug(
        "Bluesound async_unload_entry with %s: %r", entry.entry_id, entry.data
    )

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # TODO(trainman419): do we need this?
        # hass.data[DOMAIN].pop(entry.entry_id)
        pass
    return unload_ok
