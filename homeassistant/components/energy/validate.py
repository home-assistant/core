"""Validate the energy preferences provide valid data."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import dataclasses
from typing import Any

from homeassistant.components import recorder, sensor
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant, callback, valid_entity_id

from . import data
from .const import DOMAIN

ENERGY_USAGE_DEVICE_CLASSES = (sensor.DEVICE_CLASS_ENERGY,)
ENERGY_USAGE_UNITS = {
    sensor.DEVICE_CLASS_ENERGY: (ENERGY_KILO_WATT_HOUR, ENERGY_WATT_HOUR)
}
ENERGY_PRICE_UNITS = tuple(
    f"/{unit}" for units in ENERGY_USAGE_UNITS.values() for unit in units
)
ENERGY_UNIT_ERROR = "entity_unexpected_unit_energy"
ENERGY_PRICE_UNIT_ERROR = "entity_unexpected_unit_energy_price"
GAS_USAGE_DEVICE_CLASSES = (sensor.DEVICE_CLASS_ENERGY, sensor.DEVICE_CLASS_GAS)
GAS_USAGE_UNITS = {
    sensor.DEVICE_CLASS_ENERGY: (ENERGY_WATT_HOUR, ENERGY_KILO_WATT_HOUR),
    sensor.DEVICE_CLASS_GAS: (VOLUME_CUBIC_METERS, VOLUME_CUBIC_FEET),
}
GAS_PRICE_UNITS = tuple(
    f"/{unit}" for units in GAS_USAGE_UNITS.values() for unit in units
)
GAS_UNIT_ERROR = "entity_unexpected_unit_gas"
GAS_PRICE_UNIT_ERROR = "entity_unexpected_unit_gas_price"


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
    stat_value: str,
    allowed_device_classes: Sequence[str],
    allowed_units: Mapping[str, Sequence[str]],
    unit_error: str,
    result: list[ValidationIssue],
) -> None:
    """Validate a statistic."""
    has_entity_source = valid_entity_id(stat_value)

    if not has_entity_source:
        return

    if not recorder.is_entity_recorded(hass, stat_value):
        result.append(
            ValidationIssue(
                "recorder_untracked",
                stat_value,
            )
        )
        return

    state = hass.states.get(stat_value)

    if state is None:
        result.append(
            ValidationIssue(
                "entity_not_defined",
                stat_value,
            )
        )
        return

    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        result.append(ValidationIssue("entity_unavailable", stat_value, state.state))
        return

    try:
        current_value: float | None = float(state.state)
    except ValueError:
        result.append(
            ValidationIssue("entity_state_non_numeric", stat_value, state.state)
        )
        return

    if current_value is not None and current_value < 0:
        result.append(
            ValidationIssue("entity_negative_state", stat_value, current_value)
        )

    device_class = state.attributes.get(ATTR_DEVICE_CLASS)
    if device_class not in allowed_device_classes:
        result.append(
            ValidationIssue(
                "entity_unexpected_device_class",
                stat_value,
                device_class,
            )
        )
    else:
        unit = state.attributes.get("unit_of_measurement")

        if device_class and unit not in allowed_units.get(device_class, []):
            result.append(ValidationIssue(unit_error, stat_value, unit))

    state_class = state.attributes.get(sensor.ATTR_STATE_CLASS)

    allowed_state_classes = [
        sensor.STATE_CLASS_MEASUREMENT,
        sensor.STATE_CLASS_TOTAL,
        sensor.STATE_CLASS_TOTAL_INCREASING,
    ]
    if state_class not in allowed_state_classes:
        result.append(
            ValidationIssue(
                "entity_unexpected_state_class",
                stat_value,
                state_class,
            )
        )

    if (
        state_class == sensor.STATE_CLASS_MEASUREMENT
        and sensor.ATTR_LAST_RESET not in state.attributes
    ):
        result.append(
            ValidationIssue("entity_state_class_measurement_no_last_reset", stat_value)
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
    state = hass.states.get(entity_id)

    if state is None:
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
    hass: HomeAssistant, stat_id: str, result: list[ValidationIssue]
) -> None:
    """Validate that the cost stat is correct."""
    has_entity = valid_entity_id(stat_id)

    if not has_entity:
        return

    if not recorder.is_entity_recorded(hass, stat_id):
        result.append(
            ValidationIssue(
                "recorder_untracked",
                stat_id,
            )
        )

    state = hass.states.get(stat_id)

    if state is None:
        result.append(
            ValidationIssue(
                "entity_not_defined",
                stat_id,
            )
        )
        return

    state_class = state.attributes.get("state_class")

    supported_state_classes = [
        sensor.STATE_CLASS_MEASUREMENT,
        sensor.STATE_CLASS_TOTAL,
        sensor.STATE_CLASS_TOTAL_INCREASING,
    ]
    if state_class not in supported_state_classes:
        result.append(
            ValidationIssue("entity_unexpected_state_class", stat_id, state_class)
        )

    if (
        state_class == sensor.STATE_CLASS_MEASUREMENT
        and sensor.ATTR_LAST_RESET not in state.attributes
    ):
        result.append(
            ValidationIssue("entity_state_class_measurement_no_last_reset", stat_id)
        )


@callback
def _async_validate_auto_generated_cost_entity(
    hass: HomeAssistant, entity_id: str, result: list[ValidationIssue]
) -> None:
    """Validate that the auto generated cost entity is correct."""
    if not recorder.is_entity_recorded(hass, entity_id):
        result.append(
            ValidationIssue(
                "recorder_untracked",
                entity_id,
            )
        )


async def async_validate(hass: HomeAssistant) -> EnergyPreferencesValidation:
    """Validate the energy configuration."""
    manager = await data.async_get_manager(hass)

    result = EnergyPreferencesValidation()

    if manager.data is None:
        return result

    for source in manager.data["energy_sources"]:
        source_result: list[ValidationIssue] = []
        result.energy_sources.append(source_result)

        if source["type"] == "grid":
            for flow in source["flow_from"]:
                _async_validate_usage_stat(
                    hass,
                    flow["stat_energy_from"],
                    ENERGY_USAGE_DEVICE_CLASSES,
                    ENERGY_USAGE_UNITS,
                    ENERGY_UNIT_ERROR,
                    source_result,
                )

                if flow.get("stat_cost") is not None:
                    _async_validate_cost_stat(hass, flow["stat_cost"], source_result)
                elif flow.get("entity_energy_price") is not None:
                    _async_validate_price_entity(
                        hass,
                        flow["entity_energy_price"],
                        source_result,
                        ENERGY_PRICE_UNITS,
                        ENERGY_PRICE_UNIT_ERROR,
                    )

                if (
                    flow.get("entity_energy_price") is not None
                    or flow.get("number_energy_price") is not None
                ):
                    _async_validate_auto_generated_cost_entity(
                        hass,
                        hass.data[DOMAIN]["cost_sensors"][flow["stat_energy_from"]],
                        source_result,
                    )

            for flow in source["flow_to"]:
                _async_validate_usage_stat(
                    hass,
                    flow["stat_energy_to"],
                    ENERGY_USAGE_DEVICE_CLASSES,
                    ENERGY_USAGE_UNITS,
                    ENERGY_UNIT_ERROR,
                    source_result,
                )

                if flow.get("stat_compensation") is not None:
                    _async_validate_cost_stat(
                        hass, flow["stat_compensation"], source_result
                    )
                elif flow.get("entity_energy_price") is not None:
                    _async_validate_price_entity(
                        hass,
                        flow["entity_energy_price"],
                        source_result,
                        ENERGY_PRICE_UNITS,
                        ENERGY_PRICE_UNIT_ERROR,
                    )

                if (
                    flow.get("entity_energy_price") is not None
                    or flow.get("number_energy_price") is not None
                ):
                    _async_validate_auto_generated_cost_entity(
                        hass,
                        hass.data[DOMAIN]["cost_sensors"][flow["stat_energy_to"]],
                        source_result,
                    )

        elif source["type"] == "gas":
            _async_validate_usage_stat(
                hass,
                source["stat_energy_from"],
                GAS_USAGE_DEVICE_CLASSES,
                GAS_USAGE_UNITS,
                GAS_UNIT_ERROR,
                source_result,
            )

            if source.get("stat_cost") is not None:
                _async_validate_cost_stat(hass, source["stat_cost"], source_result)
            elif source.get("entity_energy_price") is not None:
                _async_validate_price_entity(
                    hass,
                    source["entity_energy_price"],
                    source_result,
                    GAS_PRICE_UNITS,
                    GAS_PRICE_UNIT_ERROR,
                )

            if (
                source.get("entity_energy_price") is not None
                or source.get("number_energy_price") is not None
            ):
                _async_validate_auto_generated_cost_entity(
                    hass,
                    hass.data[DOMAIN]["cost_sensors"][source["stat_energy_from"]],
                    source_result,
                )

        elif source["type"] == "solar":
            _async_validate_usage_stat(
                hass,
                source["stat_energy_from"],
                ENERGY_USAGE_DEVICE_CLASSES,
                ENERGY_USAGE_UNITS,
                ENERGY_UNIT_ERROR,
                source_result,
            )

        elif source["type"] == "battery":
            _async_validate_usage_stat(
                hass,
                source["stat_energy_from"],
                ENERGY_USAGE_DEVICE_CLASSES,
                ENERGY_USAGE_UNITS,
                ENERGY_UNIT_ERROR,
                source_result,
            )
            _async_validate_usage_stat(
                hass,
                source["stat_energy_to"],
                ENERGY_USAGE_DEVICE_CLASSES,
                ENERGY_USAGE_UNITS,
                ENERGY_UNIT_ERROR,
                source_result,
            )

    for device in manager.data["device_consumption"]:
        device_result: list[ValidationIssue] = []
        result.device_consumption.append(device_result)
        _async_validate_usage_stat(
            hass,
            device["stat_consumption"],
            ENERGY_USAGE_DEVICE_CLASSES,
            ENERGY_USAGE_UNITS,
            ENERGY_UNIT_ERROR,
            device_result,
        )

    return result
