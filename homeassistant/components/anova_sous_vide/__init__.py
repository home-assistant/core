"""The Anova integration."""
from __future__ import annotations

from anova_wifi import AnovaPrecisionCooker, AnovaPrecisionCookerSensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .coordinator import AnovaCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Anova from a config entry."""
    apc = AnovaPrecisionCooker(aiohttp_client.async_get_clientsession(hass))
    coordinator = AnovaCoordinator(hass, apc)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    coordinator.async_setup(
        coordinator.data["sensors"][AnovaPrecisionCookerSensor.FIRMWARE_VERSION]
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
