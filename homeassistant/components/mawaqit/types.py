"""Types for the Mawaqit integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import MosqueCoordinator, PrayerTimeCoordinator


@dataclass
class MawaqitData:
    """Runtime data for the Mawaqit integration."""

    mosque_coordinator: MosqueCoordinator
    prayer_time_coordinator: PrayerTimeCoordinator


type MawaqitConfigEntry = ConfigEntry[MawaqitData]
