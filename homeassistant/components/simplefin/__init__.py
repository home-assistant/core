"""The SimpleFIN integration."""

from simplefin4py import SimpleFin

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESS_URL
from .coordinator import SimpleFinConfigEntry, SimpleFinDataUpdateCoordinator

PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: SimpleFinConfigEntry) -> None:
    """Set up from a config entry."""
    access_url = entry.data[CONF_ACCESS_URL]
    sf_client = SimpleFin(access_url)
    sf_coordinator = SimpleFinDataUpdateCoordinator(hass, entry, sf_client)
    await sf_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = sf_coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SimpleFinConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
