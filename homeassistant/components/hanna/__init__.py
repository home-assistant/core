"""The Hanna Instruments integration."""

from __future__ import annotations

from hanna_cloud import HannaCloudClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import HannaConfigEntry
from .coordinator import HannaDataCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HannaConfigEntry) -> bool:
    """Set up Hanna Instruments from a config entry."""
    # Create a temporary API client to discover devices

    api_client = HannaCloudClient()
    await hass.async_add_executor_job(
        api_client.authenticate,
        entry.data["email"],
        entry.data["password"],
        entry.data["code"],
    )

    # Get devices
    devices = await hass.async_add_executor_job(api_client.get_devices)

    # Create device coordinators
    device_coordinators = {}
    for device in devices:
        coordinator = HannaDataCoordinator(hass, entry, device)
        await coordinator.async_config_entry_first_refresh()
        device_coordinators[coordinator.device_identifier] = coordinator

    # Set runtime data
    entry.runtime_data = {
        "device_coordinators": device_coordinators,
    }

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HannaConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clean up coordinators
    if unload_ok and entry.runtime_data:
        # Clean up device coordinators
        for coordinator in entry.runtime_data["device_coordinators"].values():
            await coordinator.async_shutdown()

        # Clear runtime data
        entry.runtime_data = None

    return unload_ok
