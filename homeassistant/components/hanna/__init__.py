"""The Hanna Instruments integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import config_entry_only_config_schema
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import HannaDataCoordinator, HannaMainCoordinator

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hanna Instruments component."""
    _ = await async_get_integration(hass, DOMAIN)
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hanna Instruments from a config entry."""

    # Create main coordinator
    main_coordinator = HannaMainCoordinator(hass, entry)
    await main_coordinator.async_authenticate(
        entry.data["email"], entry.data["password"], entry.data["code"]
    )
    await main_coordinator.async_config_entry_first_refresh()

    # Create device coordinators
    devices = await main_coordinator.async_get_devices()
    device_coordinators = {}
    for device in devices:
        coordinator = HannaDataCoordinator(hass, main_coordinator, device, entry)
        await coordinator.async_config_entry_first_refresh()
        device_coordinators[coordinator.device_identifier] = coordinator

    # Set runtime data
    entry.runtime_data = {
        "main_coordinator": main_coordinator,
        "device_coordinators": device_coordinators,
    }

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clean up coordinators
    if unload_ok and entry.runtime_data:
        # Clean up device coordinators
        for coordinator in entry.runtime_data["device_coordinators"].values():
            await coordinator.async_shutdown()

        # Clean up main coordinator
        await entry.runtime_data["main_coordinator"].async_shutdown()

        # Clear runtime data
        entry.runtime_data = None

    return unload_ok
