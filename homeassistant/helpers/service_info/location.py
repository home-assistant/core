"""Location discovery data."""

from dataclasses import dataclass

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class LocationServiceInfo(BaseServiceInfo):
    """Prepared info from location discovery."""

    latitude: float
    longitude: float
    regions: list[str]
    """The regions served by the integration that contain the home location."""
