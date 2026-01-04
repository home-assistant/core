"""Sensor platform for NRGkick."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CELLULAR_MODE_MAP,
    CONNECTOR_TYPE_MAP,
    ERROR_CODE_MAP,
    GRID_PHASES_MAP,
    RCD_TRIGGER_MAP,
    RELAY_STATE_MAP,
    STATUS_MAP,
    WARNING_CODE_MAP,
)
from .coordinator import NRGkickConfigEntry, NRGkickData, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True, init=False)
class NRGkickSensorEntityDescription(SensorEntityDescription):
    """Class describing NRGkick sensor entities."""

    value_path: tuple[str, ...]
    value_fn: Callable[[StateType], StateType] | None = None

    def __init__(
        self,
        *,
        value_path: tuple[str, ...],
        value_fn: Callable[[StateType], StateType] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the entity description.

        Args:
            value_path: Path segments to traverse inside coordinator data.
            value_fn: Optional value transform.
            **kwargs: Forwarded to Home Assistant's SensorEntityDescription.

        """
        super().__init__(**kwargs)
        object.__setattr__(self, "value_path", value_path)
        object.__setattr__(self, "value_fn", value_fn)


def _map_code_to_translation_key(
    value: StateType,
    mapping: Mapping[int, str],
    *,
    default: str = "unknown",
    normalize: Callable[[str], str] = str.lower,
) -> str:
    """Map numeric API codes to translation keys.

    The NRGkick API typically returns `int` (including `IntEnum`) values for
    code-like fields. For forward compatibility, also accept strings and
    normalize them.

    """
    if isinstance(value, int):
        return mapping.get(value, default)

    return normalize(str(value))


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick sensors based on a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    async_add_entities(
        NRGkickSensor(coordinator, description) for description in SENSORS
    )


SENSORS: tuple[NRGkickSensorEntityDescription, ...] = (
    # INFO - General
    NRGkickSensorEntityDescription(
        key="rated_current",
        translation_key="rated_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_path=("info", "general", "rated_current"),
    ),
    # INFO - Connector
    NRGkickSensorEntityDescription(
        key="connector_phase_count",
        translation_key="connector_phase_count",
        value_path=("info", "connector", "phase_count"),
    ),
    NRGkickSensorEntityDescription(
        key="connector_max_current",
        translation_key="connector_max_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_path=("info", "connector", "max_current"),
    ),
    NRGkickSensorEntityDescription(
        key="connector_type",
        translation_key="connector_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("info", "connector", "type"),
        value_fn=lambda value: _map_code_to_translation_key(value, CONNECTOR_TYPE_MAP),
    ),
    NRGkickSensorEntityDescription(
        key="connector_serial",
        translation_key="connector_serial",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("info", "connector", "serial"),
    ),
    # INFO - Grid
    NRGkickSensorEntityDescription(
        key="grid_voltage",
        translation_key="grid_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_path=("info", "grid", "voltage"),
    ),
    NRGkickSensorEntityDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        value_path=("info", "grid", "frequency"),
    ),
    NRGkickSensorEntityDescription(
        key="grid_phases",
        translation_key="grid_phases",
        value_path=("info", "grid", "phases"),
        value_fn=lambda value: _map_code_to_translation_key(
            value,
            GRID_PHASES_MAP,
            normalize=lambda text: text.lower().replace(", ", "_").replace(" ", "_"),
        ),
    ),
    # INFO - Network
    NRGkickSensorEntityDescription(
        key="network_ip_address",
        translation_key="network_ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("info", "network", "ip_address"),
    ),
    NRGkickSensorEntityDescription(
        key="network_mac_address",
        translation_key="network_mac_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("info", "network", "mac_address"),
    ),
    NRGkickSensorEntityDescription(
        key="network_ssid",
        translation_key="network_ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("info", "network", "ssid"),
    ),
    NRGkickSensorEntityDescription(
        key="network_rssi",
        translation_key="network_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("info", "network", "rssi"),
    ),
    # INFO - Cellular (optional, only if cellular module is available)
    NRGkickSensorEntityDescription(
        key="cellular_mode",
        translation_key="cellular_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=("info", "cellular", "mode"),
        value_fn=lambda value: _map_code_to_translation_key(value, CELLULAR_MODE_MAP),
    ),
    NRGkickSensorEntityDescription(
        key="cellular_rssi",
        translation_key="cellular_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=("info", "cellular", "rssi"),
    ),
    NRGkickSensorEntityDescription(
        key="cellular_operator",
        translation_key="cellular_operator",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=("info", "cellular", "operator"),
    ),
    # INFO - GPS (optional, only if GPS module is available)
    NRGkickSensorEntityDescription(
        key="gps_latitude",
        translation_key="gps_latitude",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°",
        suggested_display_precision=6,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=("info", "gps", "latitude"),
    ),
    NRGkickSensorEntityDescription(
        key="gps_longitude",
        translation_key="gps_longitude",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°",
        suggested_display_precision=6,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=("info", "gps", "longitude"),
    ),
    NRGkickSensorEntityDescription(
        key="gps_altitude",
        translation_key="gps_altitude",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="m",
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=("info", "gps", "altitude"),
    ),
    NRGkickSensorEntityDescription(
        key="gps_accuracy",
        translation_key="gps_accuracy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="m",
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=("info", "gps", "accuracy"),
    ),
    # INFO - Versions
    NRGkickSensorEntityDescription(
        key="versions_sw_sm",
        translation_key="versions_sw_sm",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=("info", "versions", "sw_sm"),
    ),
    NRGkickSensorEntityDescription(
        key="versions_hw_sm",
        translation_key="versions_hw_sm",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path=("info", "versions", "hw_sm"),
    ),
    # Control
    NRGkickSensorEntityDescription(
        key="current_set",
        translation_key="current_set",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_path=("control", "current_set"),
    ),
    NRGkickSensorEntityDescription(
        key="charge_pause",
        translation_key="charge_pause",
        value_path=("control", "charge_pause"),
    ),
    NRGkickSensorEntityDescription(
        key="energy_limit",
        translation_key="energy_limit",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=3,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_path=("control", "energy_limit"),
    ),
    NRGkickSensorEntityDescription(
        key="phase_count",
        translation_key="phase_count",
        value_path=("control", "phase_count"),
    ),
    # VALUES - Energy
    NRGkickSensorEntityDescription(
        key="total_charged_energy",
        translation_key="total_charged_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=3,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_path=("values", "energy", "total_charged_energy"),
    ),
    NRGkickSensorEntityDescription(
        key="charged_energy",
        translation_key="charged_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=3,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_path=("values", "energy", "charged_energy"),
    ),
    # VALUES - Powerflow (Total)
    NRGkickSensorEntityDescription(
        key="charging_voltage",
        translation_key="charging_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "charging_voltage"),
    ),
    NRGkickSensorEntityDescription(
        key="charging_current",
        translation_key="charging_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "charging_current"),
    ),
    NRGkickSensorEntityDescription(
        key="powerflow_grid_frequency",
        translation_key="powerflow_grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "grid_frequency"),
    ),
    NRGkickSensorEntityDescription(
        key="peak_power",
        translation_key="peak_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "peak_power"),
    ),
    NRGkickSensorEntityDescription(
        key="total_active_power",
        translation_key="total_active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "total_active_power"),
    ),
    NRGkickSensorEntityDescription(
        key="total_reactive_power",
        translation_key="total_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        value_path=("values", "powerflow", "total_reactive_power"),
    ),
    NRGkickSensorEntityDescription(
        key="total_apparent_power",
        translation_key="total_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        value_path=("values", "powerflow", "total_apparent_power"),
    ),
    NRGkickSensorEntityDescription(
        key="total_power_factor",
        translation_key="total_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_path=("values", "powerflow", "total_power_factor"),
    ),
    # VALUES - Powerflow L1
    NRGkickSensorEntityDescription(
        key="l1_voltage",
        translation_key="l1_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "l1", "voltage"),
    ),
    NRGkickSensorEntityDescription(
        key="l1_current",
        translation_key="l1_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "l1", "current"),
    ),
    NRGkickSensorEntityDescription(
        key="l1_active_power",
        translation_key="l1_active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "l1", "active_power"),
    ),
    NRGkickSensorEntityDescription(
        key="l1_reactive_power",
        translation_key="l1_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        value_path=("values", "powerflow", "l1", "reactive_power"),
    ),
    NRGkickSensorEntityDescription(
        key="l1_apparent_power",
        translation_key="l1_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        value_path=("values", "powerflow", "l1", "apparent_power"),
    ),
    NRGkickSensorEntityDescription(
        key="l1_power_factor",
        translation_key="l1_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_path=("values", "powerflow", "l1", "power_factor"),
    ),
    # VALUES - Powerflow L2
    NRGkickSensorEntityDescription(
        key="l2_voltage",
        translation_key="l2_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "l2", "voltage"),
    ),
    NRGkickSensorEntityDescription(
        key="l2_current",
        translation_key="l2_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "l2", "current"),
    ),
    NRGkickSensorEntityDescription(
        key="l2_active_power",
        translation_key="l2_active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "l2", "active_power"),
    ),
    NRGkickSensorEntityDescription(
        key="l2_reactive_power",
        translation_key="l2_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        value_path=("values", "powerflow", "l2", "reactive_power"),
    ),
    NRGkickSensorEntityDescription(
        key="l2_apparent_power",
        translation_key="l2_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        value_path=("values", "powerflow", "l2", "apparent_power"),
    ),
    NRGkickSensorEntityDescription(
        key="l2_power_factor",
        translation_key="l2_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_path=("values", "powerflow", "l2", "power_factor"),
    ),
    # VALUES - Powerflow L3
    NRGkickSensorEntityDescription(
        key="l3_voltage",
        translation_key="l3_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "l3", "voltage"),
    ),
    NRGkickSensorEntityDescription(
        key="l3_current",
        translation_key="l3_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "l3", "current"),
    ),
    NRGkickSensorEntityDescription(
        key="l3_active_power",
        translation_key="l3_active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "l3", "active_power"),
    ),
    NRGkickSensorEntityDescription(
        key="l3_reactive_power",
        translation_key="l3_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        value_path=("values", "powerflow", "l3", "reactive_power"),
    ),
    NRGkickSensorEntityDescription(
        key="l3_apparent_power",
        translation_key="l3_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        value_path=("values", "powerflow", "l3", "apparent_power"),
    ),
    NRGkickSensorEntityDescription(
        key="l3_power_factor",
        translation_key="l3_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_path=("values", "powerflow", "l3", "power_factor"),
    ),
    # VALUES - Powerflow Neutral
    NRGkickSensorEntityDescription(
        key="n_current",
        translation_key="n_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_path=("values", "powerflow", "n", "current"),
    ),
    # VALUES - General
    NRGkickSensorEntityDescription(
        key="charging_rate",
        translation_key="charging_rate",
        state_class=SensorStateClass.MEASUREMENT,
        value_path=("values", "general", "charging_rate"),
    ),
    NRGkickSensorEntityDescription(
        key="vehicle_connect_time",
        translation_key="vehicle_connect_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_path=("values", "general", "vehicle_connect_time"),
    ),
    NRGkickSensorEntityDescription(
        key="vehicle_charging_time",
        translation_key="vehicle_charging_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_path=("values", "general", "vehicle_charging_time"),
    ),
    NRGkickSensorEntityDescription(
        key="status",
        translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("values", "general", "status"),
        value_fn=lambda value: _map_code_to_translation_key(value, STATUS_MAP),
    ),
    NRGkickSensorEntityDescription(
        key="charge_permitted",
        translation_key="charge_permitted",
        value_path=("values", "general", "charge_permitted"),
    ),
    NRGkickSensorEntityDescription(
        key="relay_state",
        translation_key="relay_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("values", "general", "relay_state"),
        value_fn=lambda value: _map_code_to_translation_key(
            value,
            RELAY_STATE_MAP,
            normalize=lambda text: text.lower().replace(", ", "_").replace(" ", "_"),
        ),
    ),
    NRGkickSensorEntityDescription(
        key="charge_count",
        translation_key="charge_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_path=("values", "general", "charge_count"),
    ),
    NRGkickSensorEntityDescription(
        key="rcd_trigger",
        translation_key="rcd_trigger",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("values", "general", "rcd_trigger"),
        value_fn=lambda value: _map_code_to_translation_key(value, RCD_TRIGGER_MAP),
    ),
    NRGkickSensorEntityDescription(
        key="warning_code",
        translation_key="warning_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("values", "general", "warning_code"),
        value_fn=lambda value: _map_code_to_translation_key(value, WARNING_CODE_MAP),
    ),
    NRGkickSensorEntityDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path=("values", "general", "error_code"),
        value_fn=lambda value: _map_code_to_translation_key(value, ERROR_CODE_MAP),
    ),
    # VALUES - Temperatures
    NRGkickSensorEntityDescription(
        key="housing_temperature",
        translation_key="housing_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_path=("values", "temperatures", "housing"),
    ),
    NRGkickSensorEntityDescription(
        key="connector_l1_temperature",
        translation_key="connector_l1_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_path=("values", "temperatures", "connector_l1"),
    ),
    NRGkickSensorEntityDescription(
        key="connector_l2_temperature",
        translation_key="connector_l2_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_path=("values", "temperatures", "connector_l2"),
    ),
    NRGkickSensorEntityDescription(
        key="connector_l3_temperature",
        translation_key="connector_l3_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_path=("values", "temperatures", "connector_l3"),
    ),
    NRGkickSensorEntityDescription(
        key="domestic_plug_1_temperature",
        translation_key="domestic_plug_1_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_path=("values", "temperatures", "domestic_plug_1"),
    ),
    NRGkickSensorEntityDescription(
        key="domestic_plug_2_temperature",
        translation_key="domestic_plug_2_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_path=("values", "temperatures", "domestic_plug_2"),
    ),
)


class NRGkickSensor(NRGkickEntity, SensorEntity):
    """Representation of a NRGkick sensor."""

    entity_description: NRGkickSensorEntityDescription

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        entity_description: NRGkickSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        data: Any = self.coordinator.data
        for index, key in enumerate(self.entity_description.value_path):
            if data is None:
                return None

            # Coordinator returns a NRGkickData container; the first path segment
            # is always one of: info/control/values.
            if index == 0 and isinstance(data, NRGkickData):
                data = getattr(data, key, None)
                continue

            if not isinstance(data, dict):
                return None

            data = data.get(key)

        if self.entity_description.value_fn and data is not None:
            return self.entity_description.value_fn(cast(StateType, data))
        return cast(StateType, data)
