"""The Raspberry Pi Power Supply Checker integration."""

from rpi_bad_power import new_under_voltage

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Raspberry Pi Power Supply Checker from a config entry."""

    if await hass.async_add_executor_job(new_under_voltage) is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="under_voltage_not_supported",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
