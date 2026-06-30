"""Types for the Mawaqit integration."""

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import MosqueCoordinator, PrayerTimeCoordinator


@dataclass
class MawaqitData:
    """Runtime data for the Mawaqit integration."""

    mosque_coordinator: MosqueCoordinator
    prayer_time_coordinator: PrayerTimeCoordinator


type MawaqitConfigEntry = ConfigEntry[MawaqitData]


@dataclass
class MawaqitMosqueData:
    """Mosque data for the Mawaqit integration."""

    uuid: str
    label: str
    name: str
    latitude: float
    longitude: float
    proximity: int | None = None
    localisation: str | None = None

    @property
    def display_name(self) -> str:
        """Compute the display name for the mosque."""
        display_name = ""
        if self.proximity is not None:
            km = self.proximity / 1000
            display_name = f"{self.label} ({km:.2f} km)"
        elif self.localisation is not None:
            display_name = f"{self.label} - {self.localisation}"
        else:
            display_name = self.label

        return display_name

    @classmethod
    def from_dict(cls, data: dict) -> MawaqitMosqueData:
        """Create a MawaqitMosqueData instance from a dictionary."""
        field_names = {f.name for f in fields(cls)}

        filtered_data = {
            key: value for key, value in data.items() if key in field_names
        }

        return cls(**filtered_data)
