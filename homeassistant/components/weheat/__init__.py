"""The Weheat integration."""

from __future__ import annotations

from dataclasses import dataclass

from weheat.abstractions.discovery import HeatPumpDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import HEAT_PUMP_INFO
from .coordinator import WeheatDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class WeheatData:
    """Data for Weheat integration."""

    coordinator: WeheatDataUpdateCoordinator


type WeheatConfigEntry = ConfigEntry[WeheatData]


async def async_setup_entry(hass: HomeAssistant, entry: WeheatConfigEntry) -> bool:
    """Set up Weheat from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # Unpack the heat pump info from a dict if it is not already HeatPumpInfo
    heat_pump_info = entry.data[HEAT_PUMP_INFO]

    if isinstance(heat_pump_info, dict):
        heat_pump_info = HeatPumpDiscovery.HeatPumpInfo(**heat_pump_info)

    coordinator = WeheatDataUpdateCoordinator(
        hass=hass,
        session=session,
        heat_pump=heat_pump_info,
    )

    entry.runtime_data = WeheatData(coordinator=coordinator)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeheatConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
