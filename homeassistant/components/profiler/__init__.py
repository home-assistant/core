"""The profiler integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import LOG_INTERVAL_SUB, async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Profiler."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Profiler from a config entry."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Uses legacy hass.data[DOMAIN] pattern
    # pylint: disable-next=home-assistant-use-runtime-data
    if LOG_INTERVAL_SUB in hass.data[DOMAIN]:
        hass.data[DOMAIN][LOG_INTERVAL_SUB]()
    return True
