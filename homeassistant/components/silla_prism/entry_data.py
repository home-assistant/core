"""Runtime entry data for Silla Prism stored in hass.data."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo

if TYPE_CHECKING:
    from .coordinator import PrismCoordinator

from .solar_balance import SolarBalanceState


@dataclass(slots=True)
class RuntimeEntryData:
    """Store runtime data shared by all entities in one config entry."""

    topic: str
    ports: int
    vsensors: bool
    powerwall: bool
    serial: str
    maxcurr: int
    solar_battery_balance: bool
    battery_power_sensor: str
    solar_production_power_sensor: str
    home_load_power_sensor: str
    home_load_includes_ev: bool
    battery_soc_sensor: str
    battery_discharge_positive: bool
    battery_max_charge_power: int
    solar_balance_phases: int
    solar_balance_start_delay: int
    solar_balance_use_battery_charge: bool
    solar_balance_soc_mid: int
    solar_balance_soc_high: int
    solar_balance_mid_reserve_power: int
    solar_balance_high_reserve_power: int
    solar_balance_target_export_power: int
    solar_balance_deadband_power: int
    solar_balance_increase_interval: int
    solar_balance_increase_step: int
    solar_balance_decrease_step: int
    solar_balance_residual_export_power: int
    solar_balance_residual_export_delay: int
    solar_balance_dry_run: bool
    devices: list[DeviceInfo]
    coordinator: PrismCoordinator
    solar_balance_states: dict[int, SolarBalanceState] = field(default_factory=dict)
