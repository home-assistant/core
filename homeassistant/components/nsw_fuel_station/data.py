"""Custom types for nsw_fuel_ui."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration
    from nsw_fuel import NSWFuelApiClient

    from .coordinator import NSWFuelCoordinator


type NSWFuelConfigEntry = ConfigEntry[NSWFuelData]


@dataclass
class NSWFuelData:
    """Data for the NSWFuel Iintegration."""

    client: NSWFuelApiClient
    coordinator: NSWFuelCoordinator
    integration: Integration


StationKey = tuple[int, str]
"""
Uniquely identifies a fuel station, station codes not unique across states.

(station_code, au_state)
"""

CoordinatorData = dict[str, dict]
"""
Coordinator data payload.

{
    "favorites": {
        (station_code, au_state): {
            fuel_type: Price,
            ...
        },
        ...
    },
    "cheapest": {
        nickname: {
            fuel_type: [
                {
                    "price": float,
                    "station_code": int,
                    "station_name": str,
                    "au_state": str,
                },
                ...
            ]
        }
    }
}
"""
