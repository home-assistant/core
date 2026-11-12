"""The CPU Speed integration."""

from cpuinfo import cpuinfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up from a config entry."""
    if not await hass.async_add_executor_job(cpuinfo.get_cpu_info):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="not_compatible",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
