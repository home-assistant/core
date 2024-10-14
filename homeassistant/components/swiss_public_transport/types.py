"""Types for the swiss_public_transport integration."""

from dataclasses import dataclass

from homeassistant import config_entries

from .coordinator import SwissPublicTransportDataUpdateCoordinator

type SwissPublicTransportConfigEntry = config_entries.ConfigEntry[
    SwissPublicTransportRuntimeData
]


@dataclass
class SwissPublicTransportRuntimeData:
    """Runtime information for swiss public transport."""

    coordinator: SwissPublicTransportDataUpdateCoordinator
