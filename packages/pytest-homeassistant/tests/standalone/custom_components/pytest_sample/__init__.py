"""A custom integration used to test the installed pytest package."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the sample integration."""
    hass.states.async_set("sensor.pytest_sample", entry.data["state"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the sample integration."""
    hass.states.async_remove("sensor.pytest_sample")
    return True
