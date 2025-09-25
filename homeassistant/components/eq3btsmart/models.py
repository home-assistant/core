"""Models for eq3btsmart integration."""

from dataclasses import dataclass

from eq3btsmart.thermostat import Thermostat

from homeassistant.config_entries import ConfigEntry

from .coordinator import Eq3Coordinator


@dataclass(slots=True)
class Eq3ConfigEntryData:
    """Config entry for a single eQ-3 device."""

    thermostat: Thermostat
    coordinator: Eq3Coordinator


type Eq3ConfigEntry = ConfigEntry[Eq3ConfigEntryData]
