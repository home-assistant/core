from dataclasses import dataclass

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class LocationServiceInfo(BaseServiceInfo):
    """Information about a location service."""
