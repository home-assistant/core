"""The APsystems local API integration."""

from __future__ import annotations

from dataclasses import dataclass

from APsystemsEZ1 import APsystemsEZ1M

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT
from .coordinator import ApSystemsDataCoordinator

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]


@dataclass
class ApSystemsData:
    """Store runtime data."""

    coordinator: ApSystemsDataCoordinator
    device_id: str


type ApSystemsConfigEntry = ConfigEntry[ApSystemsData]


async def async_setup_entry(hass: HomeAssistant, entry: ApSystemsConfigEntry) -> bool:
    """Set up this integration using UI."""
    api = APsystemsEZ1M(
        ip_address=entry.data[CONF_IP_ADDRESS],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        timeout=8,
    )
    coordinator = ApSystemsDataCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    assert entry.unique_id
    entry.runtime_data = ApSystemsData(
        coordinator=coordinator, device_id=entry.unique_id
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
