"""The PECO Outage Counter integration."""

from __future__ import annotations

from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PHONE_NUMBER, DOMAIN
from .coordinator import PecoOutageCoordinator, PecoSmartMeterCoordinator

PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PECO Outage Counter from a config entry."""
    outage_coordinator = PecoOutageCoordinator(hass, entry)
    await outage_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "outage_count": outage_coordinator
    }

    if phone_number := entry.data.get(CONF_PHONE_NUMBER):
        meter_coordinator = PecoSmartMeterCoordinator(hass, entry, phone_number)
        await meter_coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id]["smart_meter"] = meter_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
