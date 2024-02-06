"""Models for eq3btsmart integration."""

from dataclasses import dataclass

from eq3btsmart.const import DEFAULT_AWAY_HOURS, DEFAULT_AWAY_TEMP
from eq3btsmart.thermostat import Thermostat

from .const import (
    DEFAULT_ADAPTER,
    DEFAULT_CURRENT_TEMP_SELECTOR,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TARGET_TEMP_SELECTOR,
    Adapter,
    CurrentTemperatureSelector,
    TargetTemperatureSelector,
)


@dataclass(slots=True)
class Eq3Config:
    """Config for a single eQ-3 device."""

    mac_address: str
    name: str
    adapter: Adapter | None = DEFAULT_ADAPTER
    current_temp_selector: CurrentTemperatureSelector = DEFAULT_CURRENT_TEMP_SELECTOR
    target_temp_selector: TargetTemperatureSelector = DEFAULT_TARGET_TEMP_SELECTOR
    external_temp_sensor: str = ""
    scan_interval: int = DEFAULT_SCAN_INTERVAL
    default_away_hours: float = DEFAULT_AWAY_HOURS
    default_away_temperature: float = DEFAULT_AWAY_TEMP


@dataclass(slots=True)
class Eq3ConfigEntry:
    """Config entry for a single eQ-3 device."""

    eq3_config: Eq3Config
    thermostat: Thermostat
