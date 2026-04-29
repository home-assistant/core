"""The PECO Outage Counter integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PHONE_NUMBER
from .coordinator import (
    PecoConfigEntry,
    PecoOutageCoordinator,
    PecoRuntimeData,
    PecoSmartMeterCoordinator,
)

PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PecoConfigEntry) -> bool:
    """Set up PECO Outage Counter from a config entry."""
    outage_coordinator = PecoOutageCoordinator(hass, entry)
    await outage_coordinator.async_config_entry_first_refresh()

    meter_coordinator: PecoSmartMeterCoordinator | None = None
    if phone_number := entry.data.get(CONF_PHONE_NUMBER):
        meter_coordinator = PecoSmartMeterCoordinator(hass, entry, phone_number)
        await meter_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = PecoRuntimeData(
        outage_coordinator=outage_coordinator,
        meter_coordinator=meter_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PecoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
