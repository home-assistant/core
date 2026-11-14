"""The SensorPush Cloud integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SensorPushCloudConfigEntry, SensorPushCloudCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: SensorPushCloudConfigEntry
) -> None:
    """Set up SensorPush Cloud from a config entry."""
    coordinator = SensorPushCloudCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: SensorPushCloudConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
