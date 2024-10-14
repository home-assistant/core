"""Types for the swiss_public_transport integration."""

from homeassistant import config_entries

from .coordinator import SwissPublicTransportDataUpdateCoordinator

type SwissPublicTransportConfigEntry = config_entries.ConfigEntry[
    SwissPublicTransportDataUpdateCoordinator
]
