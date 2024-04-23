"""Dataclass for Monzo data."""

from dataclasses import dataclass, field
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AuthenticatedMonzoAPI


@dataclass(kw_only=True)
class MonzoSensorData:
    """A dataclass for holding sensor data returned by the DataUpdateCoordinator."""

    accounts: list[dict[str, Any]] = field(default_factory=list)
    pots: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MonzoData(MonzoSensorData):
    """A dataclass for holding data stored in hass.data."""

    external_api: AuthenticatedMonzoAPI
    coordinator: DataUpdateCoordinator[MonzoSensorData]
