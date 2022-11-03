"""Validate the energy preferences provide valid data."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import dataclasses
import functools
from typing import Any

from homeassistant.components import recorder, sensor
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback, valid_entity_id

from . import data
from .const import DOMAIN

ENERGY_USAGE_DEVICE_CLASSES = (sensor.SensorDeviceClass.ENERGY,)
ENERGY_USAGE_UNITS = {
    sensor.SensorDeviceClass.ENERGY: (
        UnitOfEnergy.KILO_WATT_HOUR,
        UnitOfEnergy.MEGA_WATT_HOUR,
        UnitOfEnergy.WATT_HOUR,
        UnitOfEnergy.GIGA_JOULE,
    )
}
ENERGY_PRICE_UNITS = tuple(
    f"/{unit}" for units in ENERGY_USAGE_UNITS.values() for unit in units
)
ENERGY_UNIT_ERROR = "entity_unexpected_unit_energy"
ENERGY_PRICE_UNIT_ERROR = "entity_unexpected_unit_energy_price"
GAS_USAGE_DEVICE_CLASSES = (
    sensor.SensorDeviceClass.ENERGY,
    sensor.SensorDeviceClass.GAS,
)
GAS_USAGE_UNITS = {
    sensor.SensorDeviceClass.ENERGY: (
        UnitOfEnergy.WATT_HOUR,
        UnitOfEnergy.KILO_WATT_HOUR,
        UnitOfEnergy.MEGA_WATT_HOUR,
        UnitOfEnergy.GIGA_JOULE,
    ),
    sensor.SensorDeviceClass.GAS: (VOLUME_CUBIC_METERS, VOLUME_CUBIC_FEET),
}
GAS_PRICE_UNITS = tuple(
    f"/{unit}" for units in GAS_USAGE_UNITS.values() for unit in units
)
GAS_UNIT_ERROR = "entity_unexpected_unit_gas"
GAS_PRICE_UNIT_ERROR = "entity_unexpected_unit_gas_price"
WATER_USAGE_DEVICE_CLASSES = (sensor.SensorDeviceClass.WATER,)
WATER_USAGE_UNITS = {
    sensor.SensorDeviceClass.WATER: (
        VOLUME_CUBIC_METERS,
        VOLUME_CUBIC_FEET,
        VOLUME_GALLONS,
        VOLUME_LITERS,
    ),
}
WATER_PRICE_UNITS = tuple(
    f"/{unit}" for units in WATER_USAGE_UNITS.values() for unit in units
)
WATER_UNIT_ERROR = "entity_unexpected_unit_water"
WATER_PRICE_UNIT_ERROR = "entity_unexpected_unit_water_price"


@dataclasses.dataclass
class ValidationIssue:
    """Error or warning message."""

    type: str
    identifier: str
    value: Any | None = None


@dataclasses.dataclass
class EnergyPreferencesValidation:
    """Dictionary holding validation information."""

    energy_sources: list[list[ValidationIssue]] = dataclasses.field(
        default_factory=list
    )
    device_consumption: list[list[ValidationIssue]] = dataclasses.field(
        default_factory=list
    )

    def as_dict(self) -> dict:
        """Return dictionary version."""
        return dataclasses.asdict(self)


@callback
def _async_validate_usage_stat(
    hass: HomeAssistant,
    metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]],
    stat_id: str,
    allowed_device_classes: Sequence[str],
    allowed_units: Mapping[str, Sequence[str]],
    unit_error: str,
    result: list[ValidationIssue],
) -> None:
    """Validate a statistic."""
    if stat_id not in metadata:
        result.append(ValidationIssue("statistics_not_defined", stat_id))

    has_entity_source = valid_entity_id(stat_id)

    if not has_entity_source:
        return

    entity_id = stat_id

    if not recorder.is_entity_recorded(hass, entity_id):
        result.append(
            ValidationIssue(
                "recorder_untracked",
                entity_id,
            )
        )
        return

    if (state := hass.states.get(entity_id)) is None:
        result.append(
            ValidationIssue(
                "entity_not_defined",
                entity_id,
            )
        )
        return

    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        result.append(ValidationIssue("entity_unavailable", entity_id, state.state))
        return

    try:
        current_value: float | None = float(state.state)
    except ValueError:
        result.append(
            ValidationIssue("entity_state_non_numeric", entity_id, state.state)
        )
        return

    if current_value is not None and current_value < 0:
        result.append(
            ValidationIssue("entity_negative_state", entity_id, current_value)
        )

    device_class = state.attributes.get(ATTR_DEVICE_CLASS)
    if device_class not in allowed_device_classes:
        result.append(
            ValidationIssue(
                "entity_unexpected_device_class",
                entity_id,
                device_class,
            )
        )
    else:
        unit = state.attributes.get("unit_of_measurement")

        if device_class and unit not in allowed_units.get(device_class, []):
            result.append(ValidationIssue(unit_error, entity_id, unit))

    state_class = state.attributes.get(sensor.ATTR_STATE_CLASS)

    allowed_state_classes = [
        sensor.SensorStateClass.MEASUREMENT,
        sensor.SensorStateClass.TOTAL,
        sensor.SensorStateClass.TOTAL_INCREASING,
    ]
    if state_class not in allowed_state_classes:
        result.append(
            ValidationIssue(
                "entity_unexpected_state_class",
                entity_id,
                state_class,
            )
        )

    if (
        state_class == sensor.SensorStateClass.MEASUREMENT
        and sensor.ATTR_LAST_RESET not in state.attributes
    ):
        result.append(
            ValidationIssue("entity_state_class_measurement_no_last_reset", entity_id)
        )


@callback
def _async_validate_price_entity(
    hass: HomeAssistant,
    entity_id: str,
    result: list[ValidationIssue],
    allowed_units: tuple[str, ...],
    unit_error: str,
) -> None:
    """Validate that the price entity is correct."""
    if (state := hass.states.get(entity_id)) is None:
        result.append(
            ValidationIssue(
                "entity_not_defined",
                entity_id,
            )
        )
        return

    try:
        float(state.state)
    except ValueError:
        result.append(
            ValidationIssue("entity_state_non_numeric", entity_id, state.state)
        )
        return

    unit = state.attributes.get("unit_of_measurement")

    if unit is None or not unit.endswith(allowed_units):
        result.append(ValidationIssue(unit_error, entity_id, unit))


@callback
def _async_validate_cost_stat(
    hass: HomeAssistant,
    metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]],
    stat_id: str,
    result: list[ValidationIssue],
) -> None:
    """Validate that the cost stat is correct."""
    if stat_id not in metadata:
        result.append(ValidationIssue("statistics_not_defined", stat_id))

    has_entity = valid_entity_id(stat_id)

    if not has_entity:
        return

    if not recorder.is_entity_recorded(hass, stat_id):
        result.append(ValidationIssue("recorder_untracked", stat_id))

    if (state := hass.states.get(stat_id)) is None:
        result.append(ValidationIssue("entity_not_defined", stat_id))
        return

    state_class = state.attributes.get("state_class")

    supported_state_classes = [
        sensor.SensorStateClass.MEASUREMENT,
        sensor.SensorStateClass.TOTAL,
        sensor.SensorStateClass.TOTAL_INCREASING,
    ]
    if state_class not in supported_state_classes:
        result.append(
            ValidationIssue("entity_unexpected_state_class", stat_id, state_class)
        )

    if (
        state_class == sensor.SensorStateClass.MEASUREMENT
        and sensor.ATTR_LAST_RESET not in state.attributes
    ):
        result.append(
            ValidationIssue("entity_state_class_measurement_no_last_reset", stat_id)
        )


@callback
def _async_validate_auto_generated_cost_entity(
    hass: HomeAssistant, energy_entity_id: str, result: list[ValidationIssue]
) -> None:
    """Validate that the auto generated cost entity is correct."""
    if energy_entity_id not in hass.data[DOMAIN]["cost_sensors"]:
        # The cost entity has not been setup
        return

    cost_entity_id = hass.data[DOMAIN]["cost_sensors"][energy_entity_id]
    if not recorder.is_entity_recorded(hass, cost_entity_id):
        result.append(ValidationIssue("recorder_untracked", cost_entity_id))


async def async_validate(hass: HomeAssistant) -> EnergyPreferencesValidation:
    """Validate the energy configuration."""
    manager: data.EnergyManager = await data.async_get_manager(hass)
    statistics_metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]] = {}
    validate_calls = []
    wanted_statistics_metadata: set[str] = set()

    result = EnergyPreferencesValidation()

    if manager.data is None:
        return result

    # Create a list of validation checks
    for source in manager.data["energy_sources"]:
        source_result: list[ValidationIssue] = []
        result.energy_sources.append(source_result)

        if source["type"] == "grid":
            flow: data.FlowFromGridSourceType | data.FlowToGridSourceType
            for flow in source["flow_from"]:
                wanted_statistics_metadata.add(flow["stat_energy_from"])
                validate_calls.append(
                    functools.partial(
                        _async_validate_usage_stat,
                        hass,
                        statistics_metadata,
                        flow["stat_energy_from"],
                        ENERGY_USAGE_DEVICE_CLASSES,
                        ENERGY_USAGE_UNITS,
                        ENERGY_UNIT_ERROR,
                        source_result,
                    )
                )

                if (stat_cost := flow.get("stat_cost")) is not None:
                    wanted_statistics_metadata.add(stat_cost)
                    validate_calls.append(
                        functools.partial(
                            _async_validate_cost_stat,
                            hass,
                            statistics_metadata,
                            stat_cost,
                            source_result,
                        )
                    )
                elif flow.get("entity_energy_price") is not None:
                    validate_calls.append(
                        functools.partial(
                            _async_validate_price_entity,
                            hass,
                            flow["entity_energy_price"],
                            source_result,
                            ENERGY_PRICE_UNITS,
                            ENERGY_PRICE_UNIT_ERROR,
                        )
                    )

                if (
                    flow.get("entity_energy_price") is not None
                    or flow.get("number_energy_price") is not None
                ):
                    validate_calls.append(
                        functools.partial(
                            _async_validate_auto_generated_cost_entity,
                            hass,
                            flow["stat_energy_from"],
                            source_result,
                        )
                    )

            for flow in source["flow_to"]:
                wanted_statistics_metadata.add(flow["stat_energy_to"])
                validate_calls.append(
                    functools.partial(
                        _async_validate_usage_stat,
                        hass,
                        statistics_metadata,
                        flow["stat_energy_to"],
                        ENERGY_USAGE_DEVICE_CLASSES,
                        ENERGY_USAGE_UNITS,
                        ENERGY_UNIT_ERROR,
                        source_result,
                    )
                )

                if (stat_compensation := flow.get("stat_compensation")) is not None:
                    wanted_statistics_metadata.add(stat_compensation)
                    validate_calls.append(
                        functools.partial(
                            _async_validate_cost_stat,
                            hass,
                            statistics_metadata,
                            stat_compensation,
                            source_result,
                        )
                    )
                elif flow.get("entity_energy_price") is not None:
                    validate_calls.append(
                        functools.partial(
                            _async_validate_price_entity,
                            hass,
                            flow["entity_energy_price"],
                            source_result,
                            ENERGY_PRICE_UNITS,
                            ENERGY_PRICE_UNIT_ERROR,
                        )
                    )

                if (
                    flow.get("entity_energy_price") is not None
                    or flow.get("number_energy_price") is not None
                ):
                    validate_calls.append(
                        functools.partial(
                            _async_validate_auto_generated_cost_entity,
                            hass,
                            flow["stat_energy_to"],
                            source_result,
                        )
                    )

        elif source["type"] == "gas":
            wanted_statistics_metadata.add(source["stat_energy_from"])
            validate_calls.append(
                functools.partial(
                    _async_validate_usage_stat,
                    hass,
                    statistics_metadata,
                    source["stat_energy_from"],
                    GAS_USAGE_DEVICE_CLASSES,
                    GAS_USAGE_UNITS,
                    GAS_UNIT_ERROR,
                    source_result,
                )
            )

            if (stat_cost := source.get("stat_cost")) is not None:
                wanted_statistics_metadata.add(stat_cost)
                validate_calls.append(
                    functools.partial(
                        _async_validate_cost_stat,
                        hass,
                        statistics_metadata,
                        stat_cost,
                        source_result,
                    )
                )
            elif source.get("entity_energy_price") is not None:
                validate_calls.append(
                    functools.partial(
                        _async_validate_price_entity,
                        hass,
                        source["entity_energy_price"],
                        source_result,
                        GAS_PRICE_UNITS,
                        GAS_PRICE_UNIT_ERROR,
                    )
                )

            if (
                source.get("entity_energy_price") is not None
                or source.get("number_energy_price") is not None
            ):
                validate_calls.append(
                    functools.partial(
                        _async_validate_auto_generated_cost_entity,
                        hass,
                        source["stat_energy_from"],
                        source_result,
                    )
                )

        elif source["type"] == "water":
            wanted_statistics_metadata.add(source["stat_energy_from"])
            validate_calls.append(
                functools.partial(
                    _async_validate_usage_stat,
                    hass,
                    statistics_metadata,
                    source["stat_energy_from"],
                    WATER_USAGE_DEVICE_CLASSES,
                    WATER_USAGE_UNITS,
                    WATER_UNIT_ERROR,
                    source_result,
                )
            )

            if (stat_cost := source.get("stat_cost")) is not None:
                wanted_statistics_metadata.add(stat_cost)
                validate_calls.append(
                    functools.partial(
                        _async_validate_cost_stat,
                        hass,
                        statistics_metadata,
                        stat_cost,
                        source_result,
                    )
                )
            elif source.get("entity_energy_price") is not None:
                validate_calls.append(
                    functools.partial(
                        _async_validate_price_entity,
                        hass,
                        source["entity_energy_price"],
                        source_result,
                        WATER_PRICE_UNITS,
                        WATER_PRICE_UNIT_ERROR,
                    )
                )

            if (
                source.get("entity_energy_price") is not None
                or source.get("number_energy_price") is not None
            ):
                validate_calls.append(
                    functools.partial(
                        _async_validate_auto_generated_cost_entity,
                        hass,
                        source["stat_energy_from"],
                        source_result,
                    )
                )

        elif source["type"] == "solar":
            wanted_statistics_metadata.add(source["stat_energy_from"])
            validate_calls.append(
                functools.partial(
                    _async_validate_usage_stat,
                    hass,
                    statistics_metadata,
                    source["stat_energy_from"],
                    ENERGY_USAGE_DEVICE_CLASSES,
                    ENERGY_USAGE_UNITS,
                    ENERGY_UNIT_ERROR,
                    source_result,
                )
            )

        elif source["type"] == "battery":
            wanted_statistics_metadata.add(source["stat_energy_from"])
            validate_calls.append(
                functools.partial(
                    _async_validate_usage_stat,
                    hass,
                    statistics_metadata,
                    source["stat_energy_from"],
                    ENERGY_USAGE_DEVICE_CLASSES,
                    ENERGY_USAGE_UNITS,
                    ENERGY_UNIT_ERROR,
                    source_result,
                )
            )
            wanted_statistics_metadata.add(source["stat_energy_to"])
            validate_calls.append(
                functools.partial(
                    _async_validate_usage_stat,
                    hass,
                    statistics_metadata,
                    source["stat_energy_to"],
                    ENERGY_USAGE_DEVICE_CLASSES,
                    ENERGY_USAGE_UNITS,
                    ENERGY_UNIT_ERROR,
                    source_result,
                )
            )

    for device in manager.data["device_consumption"]:
        device_result: list[ValidationIssue] = []
        result.device_consumption.append(device_result)
        wanted_statistics_metadata.add(device["stat_consumption"])
        validate_calls.append(
            functools.partial(
                _async_validate_usage_stat,
                hass,
                statistics_metadata,
                device["stat_consumption"],
                ENERGY_USAGE_DEVICE_CLASSES,
                ENERGY_USAGE_UNITS,
                ENERGY_UNIT_ERROR,
                device_result,
            )
        )

    # Fetch the needed statistics metadata
    statistics_metadata.update(
        await recorder.get_instance(hass).async_add_executor_job(
            functools.partial(
                recorder.statistics.get_metadata,
                hass,
                statistic_ids=list(wanted_statistics_metadata),
            )
        )
    )

    # Execute all the validation checks
    for call in validate_calls:
        call()

    return result
