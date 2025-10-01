"""The Hanna Instruments integration."""

from __future__ import annotations

from hanna_cloud import HannaCloudClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_EMAIL, CONF_PASSWORD
from .coordinator import HannaConfigEntry, HannaDataCoordinator

PLATFORMS = [Platform.SENSOR]


def _authenticate_and_get_devices(
    api_client: HannaCloudClient,
    email: str,
    password: str,
) -> list:
    """Authenticate and get devices in a single executor job."""
    api_client.authenticate(email, password)
    return api_client.get_devices()


async def async_setup_entry(hass: HomeAssistant, entry: HannaConfigEntry) -> bool:
    """Set up Hanna Instruments from a config entry."""
    # Create a temporary API client to discover devices
    api_client = HannaCloudClient()
    devices = await hass.async_add_executor_job(
        _authenticate_and_get_devices,
        api_client,
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )

    # Create device coordinators
    device_coordinators = {}
    for device in devices:
        coordinator = HannaDataCoordinator(hass, entry, device, api_client)
        await coordinator.async_config_entry_first_refresh()
        device_coordinators[coordinator.device_identifier] = coordinator

    # Set runtime data
    entry.runtime_data = device_coordinators

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HannaConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clean up and device coordinators
    if unload_ok and entry.runtime_data is not None:
        for coordinator in entry.runtime_data.values():
            await coordinator.async_shutdown()

    return unload_ok
