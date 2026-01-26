"""The orvibo component."""

import logging

from orvibo.s20 import S20, S20Exception

from homeassistant import core
from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .util import S20ConfigEntry, S20Data

PLATFORMS = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: core.HomeAssistant, entry: S20ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    try:
        s20 = await hass.async_add_executor_job(
            S20,
            entry.data[CONF_HOST],
            entry.data[CONF_MAC],
        )
        _LOGGER.debug("Initialized S20 at %s", entry.data[CONF_HOST])
    except S20Exception as err:
        _LOGGER.error("S20 at %s couldn't be initialized", entry.data[CONF_HOST])

        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="init_error",
            translation_placeholders={
                "host": entry.data[CONF_HOST],
            },
        ) from err

    entry.runtime_data = S20Data(exc=S20Exception, s20=s20)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: S20ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
