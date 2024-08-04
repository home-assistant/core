"""The WeConnect integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import WeConnectCoordinator

PLATFORMS = [
    Platform.SENSOR,
]


@dataclass
class WeConnectData:
    """Class to store WeConnect runtime data."""

    coordinator: WeConnectCoordinator


type WeConnectConfigEntry = ConfigEntry[WeConnectData]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Set up the WeConnect integration."""
    coordinator = WeConnectCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = WeConnectData(coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True
