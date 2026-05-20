"""The mawaqit_prayer_times component."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MosqueCoordinator, PrayerTimeCoordinator


@dataclass
class MawaqitData:
    """Runtime data for the Mawaqit integration."""

    mosque_coordinator: MosqueCoordinator
    prayer_time_coordinator: PrayerTimeCoordinator


type MawaqitConfigEntry = ConfigEntry[MawaqitData]

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MawaqitConfigEntry
) -> bool:
    """Set up the Mawaqit Prayer Component."""
    mosque_coordinator = MosqueCoordinator(hass, config_entry)
    await mosque_coordinator.async_config_entry_first_refresh()

    prayer_time_coordinator = PrayerTimeCoordinator(hass, config_entry)
    await prayer_time_coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = MawaqitData(
        mosque_coordinator=mosque_coordinator,
        prayer_time_coordinator=prayer_time_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MawaqitConfigEntry
) -> bool:
    """Unload Mawaqit Prayer entry from config_entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
