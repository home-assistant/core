"""Validate the energy preferences provide valid data."""
from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components import recorder, sensor
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback, valid_entity_id

from . import data
from .const import DOMAIN


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
def _async_validate_energy_stat(
    hass: HomeAssistant, stat_value: str, result: list[ValidationIssue]
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

    unit = state.attributes.get("unit_of_measurement")

    if unit not in (ENERGY_KILO_WATT_HOUR, ENERGY_WATT_HOUR):
        result.append(
            ValidationIssue("entity_unexpected_unit_energy", stat_value, unit)
        )

    state_class = state.attributes.get("state_class")

    if state_class != sensor.STATE_CLASS_TOTAL_INCREASING:
        result.append(
            ValidationIssue(
                "entity_unexpected_state_class_total_increasing",
                stat_value,
                state_class,
            )
        )


@callback
def _async_validate_price_entity(
    hass: HomeAssistant, entity_id: str, result: list[ValidationIssue]
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
        value: float | None = float(state.state)
    except ValueError:
        result.append(
            ValidationIssue("entity_state_non_numeric", entity_id, state.state)
        )
        return

    if value is not None and value < 0:
        result.append(ValidationIssue("entity_negative_state", entity_id, value))

    unit = state.attributes.get("unit_of_measurement")

    if unit is None or not unit.endswith(
        (f"/{ENERGY_KILO_WATT_HOUR}", f"/{ENERGY_WATT_HOUR}")
    ):
        result.append(ValidationIssue("entity_unexpected_unit_price", entity_id, unit))


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


@callback
def _async_validate_cost_entity(
    hass: HomeAssistant, entity_id: str, result: list[ValidationIssue]
) -> None:
    """Validate that the cost entity is correct."""
    if not recorder.is_entity_recorded(hass, entity_id):
        result.append(
            ValidationIssue(
                "recorder_untracked",
                entity_id,
            )
        )

    state = hass.states.get(entity_id)

    if state is None:
        result.append(
            ValidationIssue(
                "entity_not_defined",
                entity_id,
            )
        )
        return

    state_class = state.attributes.get("state_class")

    if state_class != sensor.STATE_CLASS_TOTAL_INCREASING:
        result.append(
            ValidationIssue(
                "entity_unexpected_state_class_total_increasing", entity_id, state_class
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
                _async_validate_energy_stat(
                    hass, flow["stat_energy_from"], source_result
                )

                if flow.get("stat_cost") is not None:
                    _async_validate_cost_stat(hass, flow["stat_cost"], source_result)

                elif flow.get("entity_energy_price") is not None:
                    _async_validate_price_entity(
                        hass, flow["entity_energy_price"], source_result
                    )
                    _async_validate_cost_entity(
                        hass,
                        hass.data[DOMAIN]["cost_sensors"][flow["stat_energy_from"]],
                        source_result,
                    )

            for flow in source["flow_to"]:
                _async_validate_energy_stat(hass, flow["stat_energy_to"], source_result)

                if flow.get("stat_compensation") is not None:
                    _async_validate_cost_stat(
                        hass, flow["stat_compensation"], source_result
                    )

                elif flow.get("entity_energy_price") is not None:
                    _async_validate_price_entity(
                        hass, flow["entity_energy_price"], source_result
                    )
                    _async_validate_cost_entity(
                        hass,
                        hass.data[DOMAIN]["cost_sensors"][flow["stat_energy_to"]],
                        source_result,
                    )

        elif source["type"] == "gas":
            _async_validate_energy_stat(hass, source["stat_energy_from"], source_result)

            if source.get("stat_cost") is not None:
                _async_validate_cost_stat(hass, source["stat_cost"], source_result)

            elif source.get("entity_energy_price") is not None:
                _async_validate_price_entity(
                    hass, source["entity_energy_price"], source_result
                )
                _async_validate_cost_entity(
                    hass,
                    hass.data[DOMAIN]["cost_sensors"][source["stat_energy_from"]],
                    source_result,
                )

        elif source["type"] == "solar":
            _async_validate_energy_stat(hass, source["stat_energy_from"], source_result)

        elif source["type"] == "battery":
            _async_validate_energy_stat(hass, source["stat_energy_from"], source_result)
            _async_validate_energy_stat(hass, source["stat_energy_to"], source_result)

    for device in manager.data["device_consumption"]:
        device_result: list[ValidationIssue] = []
        result.device_consumption.append(device_result)
        _async_validate_energy_stat(hass, device["stat_consumption"], device_result)

    return result
