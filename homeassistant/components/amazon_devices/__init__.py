"""Amazon Devices integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Set up Amazon Devices platform."""

    coordinator = AmazonDevicesCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.api.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
