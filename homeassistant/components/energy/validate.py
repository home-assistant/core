"""Validate the energy preferences provide valid data."""
from __future__ import annotations

import dataclasses

from homeassistant.components import recorder
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
class ValidationMessage:
    """Error or warning message."""

    message: str
    link: str | None = None


@dataclasses.dataclass
class ValidationResult:
    """Result of validation."""

    errors: list[ValidationMessage] = dataclasses.field(default_factory=list)
    warnings: list[ValidationMessage] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class EnergyPreferencesValidation(ValidationResult):
    """Dictionary holding validation information."""

    energy_sources: list[ValidationResult] = dataclasses.field(default_factory=list)
    device_consumption: list[ValidationResult] = dataclasses.field(default_factory=list)

    def as_dict(self) -> dict:
        """Return dictionary version."""
        return dataclasses.asdict(self)


@callback
def _async_validate_energy_stat(
    hass: HomeAssistant, stat_value: str, result: ValidationResult
) -> None:
    """Validate a statistic."""
    has_entity_source = valid_entity_id(stat_value)

    if not has_entity_source:
        return

    if not recorder.is_entity_recorded(hass, stat_value):
        result.errors.append(
            ValidationMessage(
                f"Entity {stat_value} needs to be tracked by the recorder",
                "https://www.home-assistant.io/integrations/recorder#configure-filter",
            )
        )
        return

    state = hass.states.get(stat_value)

    if state is None:
        result.warnings.append(
            ValidationMessage(f"Entity {stat_value} is not currently defined")
        )
        return

    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        result.warnings.append(
            ValidationMessage(
                f"Entity {stat_value} is currently unavailable ({state.state})"
            )
        )
        return

    try:
        current_value: float | None = float(state.state)
    except ValueError:
        result.errors.append(
            ValidationMessage(
                f"Entity {stat_value} has non-numeric value {state.state}"
            )
        )
        current_value = None

    if current_value is not None and current_value < 0:
        result.errors.append(
            ValidationMessage(f"Entity {stat_value} has negative value {current_value}")
        )

    unit = state.attributes.get("unit_of_measurement")

    if unit is None:
        result.warnings.append(
            ValidationMessage(f"Entity {stat_value} has no unit of measurement")
        )

    elif unit not in (ENERGY_KILO_WATT_HOUR, ENERGY_WATT_HOUR):
        result.errors.append(
            ValidationMessage(
                f"Entity {stat_value} has an unexpected unit. Expected {ENERGY_KILO_WATT_HOUR} or {ENERGY_WATT_HOUR}"
            )
        )


@callback
def _async_validate_price_entity(
    hass: HomeAssistant, entity_id: str, result: ValidationResult
) -> None:
    """Validate that the price entity is correct."""
    state = hass.states.get(entity_id)

    if state is None:
        result.errors.append(ValidationMessage(f"Unable to find entity {entity_id}"))
        return

    try:
        value: float | None = float(state.state)
    except ValueError:
        result.errors.append(
            ValidationMessage(f"Entity {entity_id} has non-numeric value {state.state}")
        )
        value = None
        return

    if value is not None and value < 0:
        result.errors.append(
            ValidationMessage(f"Entity {entity_id} has negative value {value}")
        )

    unit = state.attributes.get("unit_of_measurement")

    if unit is None:
        result.warnings.append(
            ValidationMessage(f"Entity {entity_id} has no unit of measurement")
        )

    elif not unit.endswith((f"/{ENERGY_KILO_WATT_HOUR}", f"/{ENERGY_WATT_HOUR}")):
        result.errors.append(
            ValidationMessage(
                f"Entity {entity_id} has a unit that is not per kilowatt or watt hour"
            )
        )


@callback
def _async_validate_cost_stat(
    hass: HomeAssistant, stat_id: str, result: ValidationResult
) -> None:
    """Validate that the cost stat is correct."""
    has_entity = valid_entity_id(stat_id)

    if not has_entity:
        return

    if not recorder.is_entity_recorded(hass, stat_id):
        result.errors.append(
            ValidationMessage(
                f"Entity {stat_id} needs to be tracked by the recorder",
                "https://www.home-assistant.io/integrations/recorder#configure-filter",
            )
        )


@callback
def _async_validate_cost_entity(
    hass: HomeAssistant, entity_id: str, result: ValidationResult
) -> None:
    """Validate that the cost entity is correct."""
    if not recorder.is_entity_recorded(hass, entity_id):
        result.errors.append(
            ValidationMessage(
                f"Entity {entity_id} needs to be tracked by the recorder",
                "https://www.home-assistant.io/integrations/recorder#configure-filter",
            )
        )


async def async_validate(hass: HomeAssistant) -> EnergyPreferencesValidation:
    """Validate the energy configuration."""
    manager = await data.async_get_manager(hass)

    result = EnergyPreferencesValidation()

    if manager.data is None:
        return result

    for source in manager.data["energy_sources"]:
        source_result = ValidationResult()
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

        elif source["type"] == "solar":
            _async_validate_energy_stat(hass, source["stat_energy_from"], source_result)

        elif source["type"] == "battery":
            _async_validate_energy_stat(hass, source["stat_energy_from"], source_result)
            _async_validate_energy_stat(hass, source["stat_energy_to"], source_result)

    for device in manager.data["device_consumption"]:
        result.device_consumption.append(ValidationResult())
        _async_validate_energy_stat(
            hass, device["stat_consumption"], result.device_consumption[-1]
        )

    return result
