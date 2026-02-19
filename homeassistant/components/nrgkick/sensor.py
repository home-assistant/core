"""Sensor platform for NRGkick."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from nrgkick_api import ChargingStatus

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
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow
from homeassistant.util.variance import ignore_variance

from .const import (
    CELLULAR_MODE_MAP,
    CONNECTOR_TYPE_MAP,
    ERROR_CODE_MAP,
    RCD_TRIGGER_MAP,
    STATUS_MAP,
    WARNING_CODE_MAP,
)
from .coordinator import NRGkickConfigEntry, NRGkickData, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity

PARALLEL_UPDATES = 0


def _get_nested_dict_value(data: Any, *keys: str) -> Any:
    """Safely get a nested value from dict-like API responses."""
    current: Any = data
    for key in keys:
        try:
            current = current.get(key)
        except AttributeError:
            return None
    return current


@dataclass(frozen=True, kw_only=True)
class NRGkickSensorEntityDescription(SensorEntityDescription):
    """Class describing NRGkick sensor entities."""

    value_fn: Callable[[NRGkickData], StateType | datetime | None]
    requires_sim_module: bool = False


def _seconds_to_datetime(value: int) -> datetime:
    """Convert seconds to a UTC timestamp."""
    return utcnow().replace(microsecond=0) - timedelta(seconds=value)


_seconds_to_stable_datetime = ignore_variance(
    _seconds_to_datetime, timedelta(minutes=1)
)


def _seconds_to_stable_timestamp(value: StateType) -> datetime | None:
    """Convert seconds to a stable timestamp.

    This is used for durations that represent "seconds since X" coming from the
    device. Converting to a timestamp avoids UI drift due to polling cadence.
    """
    if value is None:
        return None

    try:
        return _seconds_to_stable_datetime(cast(int, value))
    except TypeError, OverflowError:
        return None


def _map_code_to_translation_key(
    value: StateType,
    mapping: Mapping[int, str | None],
) -> StateType:
    """Map numeric API codes to translation keys.

    The NRGkick API returns `int` (including `IntEnum`) values for code-like
    fields used as sensor states.

    """
    if value is None:
        return None

    # The API returns ints (including IntEnum). Use a cast to satisfy typing
    # without paying for repeated runtime type checks in this hot path.
    return mapping.get(cast(int, value))


def _enum_options_from_mapping(mapping: Mapping[int, str | None]) -> list[str]:
    """Build stable enum options from a numeric->translation-key mapping."""
    # Keep ordering stable by sorting keys.
    unique_options: dict[str, None] = {}
    for key in sorted(mapping):
        if (option := mapping[key]) is not None:
            unique_options[option] = None
    return list(unique_options)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick sensors based on a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    data = coordinator.data
    assert data is not None

    info_data: dict[str, Any] = data.info
    general_info: dict[str, Any] = info_data.get("general", {})
    model_type = general_info.get("model_type")

    # The cellular and GPS modules are optional. There is no dedicated API to query
    # module availability, but SIM-capable models include "SIM" in their model
    # type (e.g. "NRGkick Gen2 SIM").
    # Note: GPS to be added back with future pull request, currently only cellular.
    has_sim_module = isinstance(model_type, str) and "SIM" in model_type.upper()

    async_add_entities(
        NRGkickSensor(coordinator, description)
        for description in SENSORS
        if has_sim_module or not description.requires_sim_module
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
        value_fn=lambda data: _get_nested_dict_value(
            data.info, "general", "rated_current"
        ),
    ),
    # INFO - Connector
    NRGkickSensorEntityDescription(
        key="connector_phase_count",
        translation_key="connector_phase_count",
        value_fn=lambda data: _get_nested_dict_value(
            data.info, "connector", "phase_count"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="connector_max_current",
        translation_key="connector_max_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.info, "connector", "max_current"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="connector_type",
        translation_key="connector_type",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options_from_mapping(CONNECTOR_TYPE_MAP),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _map_code_to_translation_key(
            cast(StateType, _get_nested_dict_value(data.info, "connector", "type")),
            CONNECTOR_TYPE_MAP,
        ),
    ),
    NRGkickSensorEntityDescription(
        key="connector_serial",
        translation_key="connector_serial",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(data.info, "connector", "serial"),
    ),
    # INFO - Grid
    NRGkickSensorEntityDescription(
        key="grid_voltage",
        translation_key="grid_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(data.info, "grid", "voltage"),
    ),
    NRGkickSensorEntityDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(data.info, "grid", "frequency"),
    ),
    # INFO - Network
    NRGkickSensorEntityDescription(
        key="network_ssid",
        translation_key="network_ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(data.info, "network", "ssid"),
    ),
    NRGkickSensorEntityDescription(
        key="network_rssi",
        translation_key="network_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _get_nested_dict_value(data.info, "network", "rssi"),
    ),
    # INFO - Cellular (optional, only if cellular module is available)
    NRGkickSensorEntityDescription(
        key="cellular_mode",
        translation_key="cellular_mode",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options_from_mapping(CELLULAR_MODE_MAP),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        requires_sim_module=True,
        value_fn=lambda data: _map_code_to_translation_key(
            cast(StateType, _get_nested_dict_value(data.info, "cellular", "mode")),
            CELLULAR_MODE_MAP,
        ),
    ),
    NRGkickSensorEntityDescription(
        key="cellular_rssi",
        translation_key="cellular_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        requires_sim_module=True,
        value_fn=lambda data: _get_nested_dict_value(data.info, "cellular", "rssi"),
    ),
    NRGkickSensorEntityDescription(
        key="cellular_operator",
        translation_key="cellular_operator",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        requires_sim_module=True,
        value_fn=lambda data: _get_nested_dict_value(data.info, "cellular", "operator"),
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
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "energy", "total_charged_energy"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="charged_energy",
        translation_key="charged_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=3,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "energy", "charged_energy"
        ),
    ),
    # VALUES - Powerflow (Total)
    NRGkickSensorEntityDescription(
        key="charging_voltage",
        translation_key="charging_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "charging_voltage"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="charging_current",
        translation_key="charging_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "charging_current"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="powerflow_grid_frequency",
        translation_key="powerflow_grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "grid_frequency"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="peak_power",
        translation_key="peak_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "peak_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="total_active_power",
        translation_key="total_active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "total_active_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="total_reactive_power",
        translation_key="total_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "total_reactive_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="total_apparent_power",
        translation_key="total_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "total_apparent_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="total_power_factor",
        translation_key="total_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "total_power_factor"
        ),
    ),
    # VALUES - Powerflow L1
    NRGkickSensorEntityDescription(
        key="l1_voltage",
        translation_key="l1_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l1", "voltage"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l1_current",
        translation_key="l1_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l1", "current"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l1_active_power",
        translation_key="l1_active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l1", "active_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l1_reactive_power",
        translation_key="l1_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l1", "reactive_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l1_apparent_power",
        translation_key="l1_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l1", "apparent_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l1_power_factor",
        translation_key="l1_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l1", "power_factor"
        ),
    ),
    # VALUES - Powerflow L2
    NRGkickSensorEntityDescription(
        key="l2_voltage",
        translation_key="l2_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l2", "voltage"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l2_current",
        translation_key="l2_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l2", "current"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l2_active_power",
        translation_key="l2_active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l2", "active_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l2_reactive_power",
        translation_key="l2_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l2", "reactive_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l2_apparent_power",
        translation_key="l2_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l2", "apparent_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l2_power_factor",
        translation_key="l2_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l2", "power_factor"
        ),
    ),
    # VALUES - Powerflow L3
    NRGkickSensorEntityDescription(
        key="l3_voltage",
        translation_key="l3_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l3", "voltage"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l3_current",
        translation_key="l3_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l3", "current"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l3_active_power",
        translation_key="l3_active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=2,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l3", "active_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l3_reactive_power",
        translation_key="l3_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l3", "reactive_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l3_apparent_power",
        translation_key="l3_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l3", "apparent_power"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="l3_power_factor",
        translation_key="l3_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "l3", "power_factor"
        ),
    ),
    # VALUES - Powerflow Neutral
    NRGkickSensorEntityDescription(
        key="n_current",
        translation_key="n_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "powerflow", "n", "current"
        ),
    ),
    # VALUES - General
    NRGkickSensorEntityDescription(
        key="charging_rate",
        translation_key="charging_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "general", "charging_rate"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="vehicle_connected_since",
        translation_key="vehicle_connected_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: (
            _seconds_to_stable_timestamp(
                cast(
                    StateType,
                    _get_nested_dict_value(
                        data.values, "general", "vehicle_connect_time"
                    ),
                )
            )
            if _get_nested_dict_value(data.values, "general", "status")
            != ChargingStatus.STANDBY
            else None
        ),
    ),
    NRGkickSensorEntityDescription(
        key="vehicle_charging_time",
        translation_key="vehicle_charging_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "general", "vehicle_charging_time"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options_from_mapping(STATUS_MAP),
        value_fn=lambda data: _map_code_to_translation_key(
            cast(StateType, _get_nested_dict_value(data.values, "general", "status")),
            STATUS_MAP,
        ),
    ),
    NRGkickSensorEntityDescription(
        key="charge_count",
        translation_key="charge_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "general", "charge_count"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="rcd_trigger",
        translation_key="rcd_trigger",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options_from_mapping(RCD_TRIGGER_MAP),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _map_code_to_translation_key(
            cast(
                StateType, _get_nested_dict_value(data.values, "general", "rcd_trigger")
            ),
            RCD_TRIGGER_MAP,
        ),
    ),
    NRGkickSensorEntityDescription(
        key="warning_code",
        translation_key="warning_code",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options_from_mapping(WARNING_CODE_MAP),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _map_code_to_translation_key(
            cast(
                StateType,
                _get_nested_dict_value(data.values, "general", "warning_code"),
            ),
            WARNING_CODE_MAP,
        ),
    ),
    NRGkickSensorEntityDescription(
        key="error_code",
        translation_key="error_code",
        device_class=SensorDeviceClass.ENUM,
        options=_enum_options_from_mapping(ERROR_CODE_MAP),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _map_code_to_translation_key(
            cast(
                StateType, _get_nested_dict_value(data.values, "general", "error_code")
            ),
            ERROR_CODE_MAP,
        ),
    ),
    # VALUES - Temperatures
    NRGkickSensorEntityDescription(
        key="housing_temperature",
        translation_key="housing_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "temperatures", "housing"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="connector_l1_temperature",
        translation_key="connector_l1_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "temperatures", "connector_l1"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="connector_l2_temperature",
        translation_key="connector_l2_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "temperatures", "connector_l2"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="connector_l3_temperature",
        translation_key="connector_l3_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "temperatures", "connector_l3"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="domestic_plug_1_temperature",
        translation_key="domestic_plug_1_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "temperatures", "domestic_plug_1"
        ),
    ),
    NRGkickSensorEntityDescription(
        key="domestic_plug_2_temperature",
        translation_key="domestic_plug_2_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _get_nested_dict_value(
            data.values, "temperatures", "domestic_plug_2"
        ),
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
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
