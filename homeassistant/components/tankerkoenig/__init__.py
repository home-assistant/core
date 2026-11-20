"""Ask tankerkoenig.de for petrol price information."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import TankerkoenigConfigEntry, TankerkoenigDataUpdateCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tankerkoenig integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: TankerkoenigConfigEntry
) -> None:
    """Set a tankerkoenig configuration entry up."""
    coordinator = TankerkoenigDataUpdateCoordinator(hass, entry, DEFAULT_SCAN_INTERVAL)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: TankerkoenigConfigEntry
) -> None:
    """Unload Tankerkoenig config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
