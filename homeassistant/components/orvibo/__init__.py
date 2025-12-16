"""The orvibo component."""

from orvibo.s20 import S20, S20Exception

from homeassistant import core
from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant

from .util import S20ConfigEntry

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: core.HomeAssistant, entry: S20ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    entry.runtime_data.exc = S20Exception
    entry.runtime_data.s20 = await hass.async_add_executor_job(
        S20(
            entry.data[CONF_HOST],
            entry.data[CONF_MAC],
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: S20ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
