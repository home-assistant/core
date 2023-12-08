"""The CPU Speed integration."""
from cpuinfo import cpuinfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import LOGGER, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    if not await hass.async_add_executor_job(cpuinfo.get_cpu_info):
        LOGGER.error(
            "Unable to get CPU information, the CPU Speed integration "
            "is not compatible with your system"
        )
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
