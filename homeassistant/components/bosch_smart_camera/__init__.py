"""The Bosch Smart Camera integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import (
    BoschCameraConfigEntry,
    BoschCameraCoordinator,
    BoschFirmwareCoordinator,
)

PLATFORMS = [Platform.CAMERA, Platform.UPDATE]


async def async_setup_entry(hass: HomeAssistant, entry: BoschCameraConfigEntry) -> None:
    """Set up Bosch Smart Camera from a config entry."""
    coordinator = BoschCameraCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    coordinator.firmware = BoschFirmwareCoordinator(hass, entry, coordinator)
    await coordinator.firmware.async_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: BoschCameraConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
