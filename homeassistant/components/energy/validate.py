"""Validate the energy preferences provide valid data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import dataclasses
import functools

from homeassistant.components import recorder, sensor
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback, valid_entity_id

from . import data
from .const import DOMAIN

ENERGY_USAGE_DEVICE_CLASSES = (sensor.SensorDeviceClass.ENERGY,)
ENERGY_USAGE_UNITS: dict[str, tuple[UnitOfEnergy, ...]] = {
    sensor.SensorDeviceClass.ENERGY: tuple(UnitOfEnergy)
}
POWER_USAGE_DEVICE_CLASSES = (sensor.SensorDeviceClass.POWER,)
POWER_USAGE_UNITS: dict[str, tuple[UnitOfPower, ...]] = {
    sensor.SensorDeviceClass.POWER: tuple(UnitOfPower)
}

ENERGY_PRICE_UNITS = tuple(
    f"/{unit}" for units in ENERGY_USAGE_UNITS.values() for unit in units
)
ENERGY_UNIT_ERROR = "entity_unexpected_unit_energy"
ENERGY_PRICE_UNIT_ERROR = "entity_unexpected_unit_energy_price"
POWER_UNIT_ERROR = "entity_unexpected_unit_power"
GAS_USAGE_DEVICE_CLASSES = (
    sensor.SensorDeviceClass.ENERGY,
    sensor.SensorDeviceClass.GAS,
)
GAS_USAGE_UNITS: dict[str, tuple[UnitOfEnergy | UnitOfVolume, ...]] = {
    sensor.SensorDeviceClass.ENERGY: ENERGY_USAGE_UNITS[
        sensor.SensorDeviceClass.ENERGY
    ],
    sensor.SensorDeviceClass.GAS: (
        UnitOfVolume.CENTUM_CUBIC_FEET,
        UnitOfVolume.CUBIC_FEET,
        UnitOfVolume.CUBIC_METERS,
        UnitOfVolume.LITERS,
        UnitOfVolume.MILLE_CUBIC_FEET,
    ),
}
GAS_PRICE_UNITS = tuple(
    f"/{unit}" for units in GAS_USAGE_UNITS.values() for unit in units
)
GAS_UNIT_ERROR = "entity_unexpected_unit_gas"
GAS_PRICE_UNIT_ERROR = "entity_unexpected_unit_gas_price"
WATER_USAGE_DEVICE_CLASSES = (sensor.SensorDeviceClass.WATER,)
WATER_USAGE_UNITS: dict[str, tuple[UnitOfVolume, ...]] = {
    sensor.SensorDeviceClass.WATER: (
        UnitOfVolume.CENTUM_CUBIC_FEET,
        UnitOfVolume.CUBIC_FEET,
        UnitOfVolume.CUBIC_METERS,
        UnitOfVolume.GALLONS,
        UnitOfVolume.LITERS,
        UnitOfVolume.MILLE_CUBIC_FEET,
    ),
}
WATER_PRICE_UNITS = tuple(
    f"/{unit}" for units in WATER_USAGE_UNITS.values() for unit in units
)
WATER_UNIT_ERROR = "entity_unexpected_unit_water"
WATER_PRICE_UNIT_ERROR = "entity_unexpected_unit_water_price"


def _get_placeholders(hass: HomeAssistant, issue_type: str) -> dict[str, str] | None:
    currency = hass.config.currency
    if issue_type == ENERGY_UNIT_ERROR:
        return {
            "energy_units": ", ".join(
                ENERGY_USAGE_UNITS[sensor.SensorDeviceClass.ENERGY]
            ),
        }
    if issue_type == ENERGY_PRICE_UNIT_ERROR:
        return {
            "price_units": ", ".join(
                f"{currency}{unit}" for unit in ENERGY_PRICE_UNITS
            ),
        }
    if issue_type == POWER_UNIT_ERROR:
        return {
            "power_units": ", ".join(POWER_USAGE_UNITS[sensor.SensorDeviceClass.POWER]),
        }
    if issue_type == GAS_UNIT_ERROR:
        return {
            "energy_units": ", ".join(GAS_USAGE_UNITS[sensor.SensorDeviceClass.ENERGY]),
            "gas_units": ", ".join(GAS_USAGE_UNITS[sensor.SensorDeviceClass.GAS]),
        }
    if issue_type == GAS_PRICE_UNIT_ERROR:
        return {
            "price_units": ", ".join(f"{currency}{unit}" for unit in GAS_PRICE_UNITS),
        }
    if issue_type == WATER_UNIT_ERROR:
        return {
            "water_units": ", ".join(WATER_USAGE_UNITS[sensor.SensorDeviceClass.WATER]),
        }
    if issue_type == WATER_PRICE_UNIT_ERROR:
        return {
            "price_units": ", ".join(f"{currency}{unit}" for unit in WATER_PRICE_UNITS),
        }
    return None


@dataclasses.dataclass(slots=True)
class ValidationIssue:
    """Error or warning message."""

    type: str
    affected_entities: set[tuple[str, float | str | None]] = dataclasses.field(
        default_factory=set
    )
    translation_placeholders: dict[str, str] | None = None


@dataclasses.dataclass(slots=True)
class ValidationIssues:
    """Container for validation issues."""

    issues: dict[str, ValidationIssue] = dataclasses.field(default_factory=dict)

    def __init__(self) -> None:
        """Container for validiation issues."""
        self.issues = {}

    def add_issue(
        self,
        hass: HomeAssistant,
        issue_type: str,
        affected_entity: str,
        detail: float | str | None = None,
    ) -> None:
        """Add an issue for an entity."""
        if not (issue := self.issues.get(issue_type)):
            self.issues[issue_type] = issue = ValidationIssue(issue_type)
            issue.translation_placeholders = _get_placeholders(hass, issue_type)
        issue.affected_entities.add((affected_entity, detail))


@dataclasses.dataclass(slots=True)
class EnergyPreferencesValidation:
    """Dictionary holding validation information."""

    energy_sources: list[ValidationIssues] = dataclasses.field(default_factory=list)
    device_consumption: list[ValidationIssues] = dataclasses.field(default_factory=list)
    device_consumption_water: list[ValidationIssues] = dataclasses.field(
        default_factory=list
    )

    def as_dict(self) -> dict:
        """Return dictionary version."""
        return {
            "energy_sources": [
                [dataclasses.asdict(issue) for issue in issues.issues.values()]
                for issues in self.energy_sources
            ],
            "device_consumption": [
                [dataclasses.asdict(issue) for issue in issues.issues.values()]
                for issues in self.device_consumption
            ],
            "device_consumption_water": [
                [dataclasses.asdict(issue) for issue in issues.issues.values()]
                for issues in self.device_consumption_water
            ],
        }


@callback
def _async_validate_stat_common(
    hass: HomeAssistant,
    metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]],
    stat_id: str,
    allowed_device_classes: Sequence[str],
    allowed_units: Mapping[str, Sequence[str]],
    unit_error: str,
    issues: ValidationIssues,
    check_negative: bool = False,
) -> str | None:
    """Validate common aspects of a statistic.

    Returns the entity_id if validation succeeds, None otherwise.
    """
    if stat_id not in metadata:
        issues.add_issue(hass, "statistics_not_defined", stat_id)

    has_entity_source = valid_entity_id(stat_id)

    if not has_entity_source:
        return None

    entity_id = stat_id

    if not recorder.is_entity_recorded(hass, entity_id):
        issues.add_issue(hass, "recorder_untracked", entity_id)
        return None

    if (state := hass.states.get(entity_id)) is None:
        issues.add_issue(hass, "entity_not_defined", entity_id)
        return None

    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        issues.add_issue(hass, "entity_unavailable", entity_id, state.state)
        return None

    try:
        current_value: float | None = float(state.state)
    except ValueError:
        issues.add_issue(hass, "entity_state_non_numeric", entity_id, state.state)
        return None

    if check_negative and current_value is not None and current_value < 0:
        issues.add_issue(hass, "entity_negative_state", entity_id, current_value)

    device_class = state.attributes.get(ATTR_DEVICE_CLASS)
    if device_class not in allowed_device_classes:
        issues.add_issue(
            hass, "entity_unexpected_device_class", entity_id, device_class
        )
    else:
        unit = state.attributes.get("unit_of_measurement")

        if device_class and unit not in allowed_units.get(device_class, []):
            issues.add_issue(hass, unit_error, entity_id, unit)

    return entity_id


@callback
def _async_validate_usage_stat(
    hass: HomeAssistant,
    metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]],
    stat_id: str,
    allowed_device_classes: Sequence[str],
    allowed_units: Mapping[str, Sequence[str]],
    unit_error: str,
    issues: ValidationIssues,
) -> None:
    """Validate a statistic."""
    entity_id = _async_validate_stat_common(
        hass,
        metadata,
        stat_id,
        allowed_device_classes,
        allowed_units,
        unit_error,
        issues,
        check_negative=True,
    )

    if entity_id is None:
        return

    state = hass.states.get(entity_id)
    assert state is not None
    state_class = state.attributes.get(sensor.ATTR_STATE_CLASS)

    allowed_state_classes = [
        sensor.SensorStateClass.MEASUREMENT,
        sensor.SensorStateClass.TOTAL,
        sensor.SensorStateClass.TOTAL_INCREASING,
    ]
    if state_class not in allowed_state_classes:
        issues.add_issue(hass, "entity_unexpected_state_class", entity_id, state_class)

    if (
        state_class == sensor.SensorStateClass.MEASUREMENT
        and sensor.ATTR_LAST_RESET not in state.attributes
    ):
        issues.add_issue(
            hass, "entity_state_class_measurement_no_last_reset", entity_id
        )


@callback
def _async_validate_price_entity(
    hass: HomeAssistant,
    entity_id: str,
    issues: ValidationIssues,
    allowed_units: tuple[str, ...],
    unit_error: str,
) -> None:
    """Validate that the price entity is correct."""
    if (state := hass.states.get(entity_id)) is None:
        issues.add_issue(hass, "entity_not_defined", entity_id)
        return

    try:
        float(state.state)
    except ValueError:
        issues.add_issue(hass, "entity_state_non_numeric", entity_id, state.state)
        return

    unit = state.attributes.get("unit_of_measurement")

    if unit is None or not unit.endswith(allowed_units):
        issues.add_issue(hass, unit_error, entity_id, unit)


@callback
def _async_validate_power_stat(
    hass: HomeAssistant,
    metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]],
    stat_id: str,
    allowed_device_classes: Sequence[str],
    allowed_units: Mapping[str, Sequence[str]],
    unit_error: str,
    issues: ValidationIssues,
) -> None:
    """Validate a power statistic."""
    entity_id = _async_validate_stat_common(
        hass,
        metadata,
        stat_id,
        allowed_device_classes,
        allowed_units,
        unit_error,
        issues,
        check_negative=False,
    )

    if entity_id is None:
        return

    state = hass.states.get(entity_id)
    assert state is not None
    state_class = state.attributes.get(sensor.ATTR_STATE_CLASS)

    if state_class != sensor.SensorStateClass.MEASUREMENT:
        issues.add_issue(hass, "entity_unexpected_state_class", entity_id, state_class)


@callback
def _async_validate_cost_stat(
    hass: HomeAssistant,
    metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]],
    stat_id: str,
    issues: ValidationIssues,
) -> None:
    """Validate that the cost stat is correct."""
    if stat_id not in metadata:
        issues.add_issue(hass, "statistics_not_defined", stat_id)

    has_entity = valid_entity_id(stat_id)

    if not has_entity:
        return

    if not recorder.is_entity_recorded(hass, stat_id):
        issues.add_issue(hass, "recorder_untracked", stat_id)

    if (state := hass.states.get(stat_id)) is None:
        issues.add_issue(hass, "entity_not_defined", stat_id)
        return

    state_class = state.attributes.get("state_class")

    supported_state_classes = [
        sensor.SensorStateClass.MEASUREMENT,
        sensor.SensorStateClass.TOTAL,
        sensor.SensorStateClass.TOTAL_INCREASING,
    ]
    if state_class not in supported_state_classes:
        issues.add_issue(hass, "entity_unexpected_state_class", stat_id, state_class)

    if (
        state_class == sensor.SensorStateClass.MEASUREMENT
        and sensor.ATTR_LAST_RESET not in state.attributes
    ):
        issues.add_issue(hass, "entity_state_class_measurement_no_last_reset", stat_id)


@callback
def _async_validate_auto_generated_cost_entity(
    hass: HomeAssistant, energy_entity_id: str, issues: ValidationIssues
) -> None:
    """Validate that the auto generated cost entity is correct."""
    if energy_entity_id not in hass.data[DOMAIN]["cost_sensors"]:
        # The cost entity has not been setup
        return

    cost_entity_id = hass.data[DOMAIN]["cost_sensors"][energy_entity_id]
    if not recorder.is_entity_recorded(hass, cost_entity_id):
        issues.add_issue(hass, "recorder_untracked", cost_entity_id)


def _validate_grid_source(
    hass: HomeAssistant,
    source: data.GridSourceType,
    statistics_metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]],
    wanted_statistics_metadata: set[str],
    source_result: ValidationIssues,
    validate_calls: list[functools.partial[None]],
) -> None:
    """Validate grid energy source."""
    flow_from: data.FlowFromGridSourceType
    for flow_from in source["flow_from"]:
        wanted_statistics_metadata.add(flow_from["stat_energy_from"])
        validate_calls.append(
            functools.partial(
                _async_validate_usage_stat,
                hass,
                statistics_metadata,
                flow_from["stat_energy_from"],
                ENERGY_USAGE_DEVICE_CLASSES,
                ENERGY_USAGE_UNITS,
                ENERGY_UNIT_ERROR,
                source_result,
            )
        )

        if (stat_cost := flow_from.get("stat_cost")) is not None:
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
        elif (entity_energy_price := flow_from.get("entity_energy_price")) is not None:
            validate_calls.append(
                functools.partial(
                    _async_validate_price_entity,
                    hass,
                    entity_energy_price,
                    source_result,
                    ENERGY_PRICE_UNITS,
                    ENERGY_PRICE_UNIT_ERROR,
                )
            )

        if (
            flow_from.get("entity_energy_price") is not None
            or flow_from.get("number_energy_price") is not None
        ):
            validate_calls.append(
                functools.partial(
                    _async_validate_auto_generated_cost_entity,
                    hass,
                    flow_from["stat_energy_from"],
                    source_result,
                )
            )

    flow_to: data.FlowToGridSourceType
    for flow_to in source["flow_to"]:
        wanted_statistics_metadata.add(flow_to["stat_energy_to"])
        validate_calls.append(
            functools.partial(
                _async_validate_usage_stat,
                hass,
                statistics_metadata,
                flow_to["stat_energy_to"],
                ENERGY_USAGE_DEVICE_CLASSES,
                ENERGY_USAGE_UNITS,
                ENERGY_UNIT_ERROR,
                source_result,
            )
        )

        if (stat_compensation := flow_to.get("stat_compensation")) is not None:
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
        elif (entity_energy_price := flow_to.get("entity_energy_price")) is not None:
            validate_calls.append(
                functools.partial(
                    _async_validate_price_entity,
                    hass,
                    entity_energy_price,
                    source_result,
                    ENERGY_PRICE_UNITS,
                    ENERGY_PRICE_UNIT_ERROR,
                )
            )

        if (
            flow_to.get("entity_energy_price") is not None
            or flow_to.get("number_energy_price") is not None
        ):
            validate_calls.append(
                functools.partial(
                    _async_validate_auto_generated_cost_entity,
                    hass,
                    flow_to["stat_energy_to"],
                    source_result,
                )
            )

    for power_stat in source.get("power", []):
        wanted_statistics_metadata.add(power_stat["stat_rate"])
        validate_calls.append(
            functools.partial(
                _async_validate_power_stat,
                hass,
                statistics_metadata,
                power_stat["stat_rate"],
                POWER_USAGE_DEVICE_CLASSES,
                POWER_USAGE_UNITS,
                POWER_UNIT_ERROR,
                source_result,
            )
        )


def _validate_gas_source(
    hass: HomeAssistant,
    source: data.GasSourceType,
    statistics_metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]],
    wanted_statistics_metadata: set[str],
    source_result: ValidationIssues,
    validate_calls: list[functools.partial[None]],
) -> None:
    """Validate gas energy source."""
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
    elif (entity_energy_price := source.get("entity_energy_price")) is not None:
        validate_calls.append(
            functools.partial(
                _async_validate_price_entity,
                hass,
                entity_energy_price,
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


def _validate_water_source(
    hass: HomeAssistant,
    source: data.WaterSourceType,
    statistics_metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]],
    wanted_statistics_metadata: set[str],
    source_result: ValidationIssues,
    validate_calls: list[functools.partial[None]],
) -> None:
    """Validate water energy source."""
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
    elif (entity_energy_price := source.get("entity_energy_price")) is not None:
        validate_calls.append(
            functools.partial(
                _async_validate_price_entity,
                hass,
                entity_energy_price,
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


async def async_validate(hass: HomeAssistant) -> EnergyPreferencesValidation:
    """Validate the energy configuration."""
    manager: data.EnergyManager = await data.async_get_manager(hass)
    statistics_metadata: dict[str, tuple[int, recorder.models.StatisticMetaData]] = {}
    validate_calls: list[functools.partial[None]] = []
    wanted_statistics_metadata: set[str] = set()

    result = EnergyPreferencesValidation()

    if manager.data is None:
        return result

    # Create a list of validation checks
    for source in manager.data["energy_sources"]:
        source_result = ValidationIssues()
        result.energy_sources.append(source_result)

        if source["type"] == "grid":
            _validate_grid_source(
                hass,
                source,
                statistics_metadata,
                wanted_statistics_metadata,
                source_result,
                validate_calls,
            )

        elif source["type"] == "gas":
            _validate_gas_source(
                hass,
                source,
                statistics_metadata,
                wanted_statistics_metadata,
                source_result,
                validate_calls,
            )

        elif source["type"] == "water":
            _validate_water_source(
                hass,
                source,
                statistics_metadata,
                wanted_statistics_metadata,
                source_result,
                validate_calls,
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
        device_result = ValidationIssues()
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

    for device in manager.data.get("device_consumption_water", []):
        device_result = ValidationIssues()
        result.device_consumption_water.append(device_result)
        wanted_statistics_metadata.add(device["stat_consumption"])
        validate_calls.append(
            functools.partial(
                _async_validate_usage_stat,
                hass,
                statistics_metadata,
                device["stat_consumption"],
                WATER_USAGE_DEVICE_CLASSES,
                WATER_USAGE_UNITS,
                WATER_UNIT_ERROR,
                device_result,
            )
        )

    # Fetch the needed statistics metadata
    statistics_metadata.update(
        await recorder.get_instance(hass).async_add_executor_job(
            functools.partial(
                recorder.statistics.get_metadata,
                hass,
                statistic_ids=set(wanted_statistics_metadata),
            )
        )
    )

    # Execute all the validation checks
    for call in validate_calls:
        call()

    return result
