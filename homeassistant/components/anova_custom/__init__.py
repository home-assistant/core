"""The Anova integration."""

from __future__ import annotations

from anova_wifi import AnovaPrecisionCooker, AnovaPrecisionCookerSensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .coordinator import AnovaCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Anova from a config entry."""
    devices = [
        AnovaPrecisionCooker(
            aiohttp_client.async_get_clientsession(hass),
            device[0],
            device[1],
            entry.data["jwt"],
        )
        for device in entry.data["devices"]
    ]
    coordinators = {
        device.device_key: AnovaCoordinator(hass, device) for device in devices
    }
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()
        firmware_version = coordinator.data["sensors"][
            AnovaPrecisionCookerSensor.FIRMWARE_VERSION
        ]
        coordinator.async_setup(firmware_version)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
