"""The Bosch Alarm integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import BoschAlarmConfigEntry, BoschAlarmCoordinator

PLATFORMS: list[Platform] = [Platform.ALARM_CONTROL_PANEL]


async def async_setup_entry(hass: HomeAssistant, entry: BoschAlarmConfigEntry) -> bool:
    """Set up Bosch Alarm from a config entry."""

    coordinator = BoschAlarmCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=f"Bosch {coordinator.panel.model}",
        manufacturer="Bosch Security Systems",
        model=coordinator.panel.model,
        sw_version=coordinator.panel.firmware_version,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BoschAlarmConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
