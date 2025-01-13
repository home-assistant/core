"""The Actron Air Neo integration models."""

from __future__ import annotations

from dataclasses import dataclass

from actron_neo_api import ActronNeoAPI

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .climate import ActronAirNeoACUnit


@dataclass
class ActronAirNeoData:
    """Data for the Actron Air Neo integration."""

    pairing_token: str
    coordinator: DataUpdateCoordinator
    api: ActronNeoAPI
    ac_unit: ActronAirNeoACUnit
    serial_number: str
