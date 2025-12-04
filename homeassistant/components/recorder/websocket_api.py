"""The Recorder websocket API."""

from __future__ import annotations

import asyncio
from datetime import datetime as dt
import logging
from typing import Any, Literal, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import messages
from homeassistant.core import HomeAssistant, callback, valid_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    ApparentPowerConverter,
    AreaConverter,
    BloodGlucoseConcentrationConverter,
    CarbonMonoxideConcentrationConverter,
    ConductivityConverter,
    DataRateConverter,
    DistanceConverter,
    DurationConverter,
    ElectricCurrentConverter,
    ElectricPotentialConverter,
    EnergyConverter,
    EnergyDistanceConverter,
    InformationConverter,
    MassConverter,
    MassVolumeConcentrationConverter,
    PowerConverter,
    PressureConverter,
    ReactiveEnergyConverter,
    ReactivePowerConverter,
    SpeedConverter,
    TemperatureConverter,
    TemperatureDeltaConverter,
    UnitlessRatioConverter,
    VolumeConverter,
    VolumeFlowRateConverter,
)

from .models import StatisticMeanType, StatisticPeriod
from .queries import get_entity_disk_usage, get_entity_disk_usage_limited
from .statistics import (
    UNIT_CLASS_TO_UNIT_CONVERTER,
    async_add_external_statistics,
    async_change_statistics_unit,
    async_import_statistics,
    async_list_statistic_ids,
    async_update_statistics_metadata,
    list_statistic_ids,
    statistic_during_period,
    statistics_during_period,
    update_statistics_issues,
    validate_statistics,
)
from .util import PERIOD_SCHEMA, get_instance, resolve_period, session_scope

_LOGGER = logging.getLogger(__name__)

CLEAR_STATISTICS_TIME_OUT = 10
UPDATE_STATISTICS_METADATA_TIME_OUT = 10

UNIT_SCHEMA = vol.Schema(
    {
        vol.Optional("apparent_power"): vol.In(ApparentPowerConverter.VALID_UNITS),
        vol.Optional("area"): vol.In(AreaConverter.VALID_UNITS),
        vol.Optional("blood_glucose_concentration"): vol.In(
            BloodGlucoseConcentrationConverter.VALID_UNITS
        ),
        vol.Optional("carbon_monoxide"): vol.In(
            CarbonMonoxideConcentrationConverter.VALID_UNITS
        ),
        vol.Optional("concentration"): vol.In(
            MassVolumeConcentrationConverter.VALID_UNITS
        ),
        vol.Optional("conductivity"): vol.In(ConductivityConverter.VALID_UNITS),
        vol.Optional("data_rate"): vol.In(DataRateConverter.VALID_UNITS),
        vol.Optional("distance"): vol.In(DistanceConverter.VALID_UNITS),
        vol.Optional("duration"): vol.In(DurationConverter.VALID_UNITS),
        vol.Optional("electric_current"): vol.In(ElectricCurrentConverter.VALID_UNITS),
        vol.Optional("voltage"): vol.In(ElectricPotentialConverter.VALID_UNITS),
        vol.Optional("energy"): vol.In(EnergyConverter.VALID_UNITS),
        vol.Optional("energy_distance"): vol.In(EnergyDistanceConverter.VALID_UNITS),
        vol.Optional("information"): vol.In(InformationConverter.VALID_UNITS),
        vol.Optional("mass"): vol.In(MassConverter.VALID_UNITS),
        vol.Optional("power"): vol.In(PowerConverter.VALID_UNITS),
        vol.Optional("pressure"): vol.In(PressureConverter.VALID_UNITS),
        vol.Optional("reactive_energy"): vol.In(ReactiveEnergyConverter.VALID_UNITS),
        vol.Optional("reactive_power"): vol.In(ReactivePowerConverter.VALID_UNITS),
        vol.Optional("speed"): vol.In(SpeedConverter.VALID_UNITS),
        vol.Optional("temperature"): vol.In(TemperatureConverter.VALID_UNITS),
        vol.Optional("temperature_delta"): vol.In(
            TemperatureDeltaConverter.VALID_UNITS
        ),
        vol.Optional("unitless"): vol.In(UnitlessRatioConverter.VALID_UNITS),
        vol.Optional("volume"): vol.In(VolumeConverter.VALID_UNITS),
        vol.Optional("volume_flow_rate"): vol.In(VolumeFlowRateConverter.VALID_UNITS),
    }
)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorder websocket API."""
    websocket_api.async_register_command(hass, ws_adjust_sum_statistics)
    websocket_api.async_register_command(hass, ws_change_statistics_unit)
    websocket_api.async_register_command(hass, ws_clear_statistics)
    websocket_api.async_register_command(hass, ws_get_entity_disk_usage)
    websocket_api.async_register_command(hass, ws_get_entity_exclusions)
    websocket_api.async_register_command(hass, ws_get_statistic_during_period)
    websocket_api.async_register_command(hass, ws_get_statistics_during_period)
    websocket_api.async_register_command(hass, ws_get_statistics_metadata)
    websocket_api.async_register_command(hass, ws_list_statistic_ids)
    websocket_api.async_register_command(hass, ws_import_statistics)
    websocket_api.async_register_command(hass, ws_update_entity_exclusions)
    websocket_api.async_register_command(hass, ws_update_statistics_issues)
    websocket_api.async_register_command(hass, ws_update_statistics_metadata)
    websocket_api.async_register_command(hass, ws_validate_statistics)


def _get_entity_disk_usage_data(
    hass: HomeAssistant, limit: int | None
) -> list[dict[str, Any]]:
    """Get entity disk usage data in the executor."""
    with session_scope(hass=hass, read_only=True) as session:
        if limit is not None:
            stmt = get_entity_disk_usage_limited(limit)
        else:
            stmt = get_entity_disk_usage()
        result = session.execute(stmt)
        return [
            {
                "entity_id": row.entity_id,
                "state_count": row.state_count,
                "estimated_bytes": row.estimated_bytes or 0,
            }
            for row in result
        ]


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/get_entity_disk_usage",
        vol.Optional("limit"): cv.positive_int,
    }
)
@websocket_api.async_response
async def ws_get_entity_disk_usage(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return disk usage statistics per entity.

    Returns a list of entities sorted by disk usage (descending), with:
    - entity_id: The entity identifier
    - state_count: Number of state records
    - estimated_bytes: Estimated disk usage in bytes
    """
    instance = get_instance(hass)
    result = await instance.async_add_executor_job(
        _get_entity_disk_usage_data, hass, msg.get("limit")
    )
    connection.send_result(msg["id"], result)


def _ws_get_statistic_during_period(
    hass: HomeAssistant,
    msg_id: int,
    start_time: dt | None,
    end_time: dt | None,
    statistic_id: str,
    types: set[Literal["max", "mean", "min", "change"]] | None,
    units: dict[str, str],
) -> bytes:
    """Fetch statistics and convert them to json in the executor."""
    return json_bytes(
        messages.result_message(
            msg_id,
            statistic_during_period(
                hass, start_time, end_time, statistic_id, types, units=units
            ),
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/statistic_during_period",
        vol.Required("statistic_id"): str,
        vol.Optional("types"): vol.All(
            [vol.Any("max", "mean", "min", "change")], vol.Coerce(set)
        ),
        vol.Optional("units"): UNIT_SCHEMA,
        **PERIOD_SCHEMA.schema,
    }
)
@websocket_api.async_response
async def ws_get_statistic_during_period(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle statistics websocket command."""
    if ("start_time" in msg or "end_time" in msg) and "duration" in msg:
        raise HomeAssistantError
    if "offset" in msg and "duration" not in msg:
        raise HomeAssistantError

    start_time, end_time = resolve_period(cast(StatisticPeriod, msg))

    connection.send_message(
        await get_instance(hass).async_add_executor_job(
            _ws_get_statistic_during_period,
            hass,
            msg["id"],
            start_time,
            end_time,
            msg["statistic_id"],
            msg.get("types"),
            msg.get("units"),
        )
    )


def _ws_get_statistics_during_period(
    hass: HomeAssistant,
    msg_id: int,
    start_time: dt,
    end_time: dt | None,
    statistic_ids: set[str] | None,
    period: Literal["5minute", "day", "hour", "week", "month"],
    units: dict[str, str],
    types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]],
) -> bytes:
    """Fetch statistics and convert them to json in the executor."""
    result = statistics_during_period(
        hass,
        start_time,
        end_time,
        statistic_ids,
        period,
        units,
        types,
    )
    include_last_reset = "last_reset" in types
    for statistic_rows in result.values():
        for row in statistic_rows:
            row["start"] = int(row["start"] * 1000)
            row["end"] = int(row["end"] * 1000)
            if include_last_reset and (last_reset := row["last_reset"]) is not None:
                row["last_reset"] = int(last_reset * 1000)
    return json_bytes(messages.result_message(msg_id, result))


async def ws_handle_get_statistics_during_period(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Handle statistics websocket command."""
    start_time_str = msg["start_time"]
    end_time_str = msg.get("end_time")

    if start_time := dt_util.parse_datetime(start_time_str):
        start_time = dt_util.as_utc(start_time)
    else:
        connection.send_error(msg["id"], "invalid_start_time", "Invalid start_time")
        return

    if end_time_str:
        if end_time := dt_util.parse_datetime(end_time_str):
            end_time = dt_util.as_utc(end_time)
        else:
            connection.send_error(msg["id"], "invalid_end_time", "Invalid end_time")
            return
    else:
        end_time = None

    if (types := msg.get("types")) is None:
        types = {"change", "last_reset", "max", "mean", "min", "state", "sum"}
    connection.send_message(
        await get_instance(hass).async_add_executor_job(
            _ws_get_statistics_during_period,
            hass,
            msg["id"],
            start_time,
            end_time,
            set(msg["statistic_ids"]),
            msg.get("period"),
            msg.get("units"),
            types,
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/statistics_during_period",
        vol.Required("start_time"): str,
        vol.Optional("end_time"): str,
        vol.Required("statistic_ids"): vol.All([str], vol.Length(min=1)),
        vol.Required("period"): vol.Any("5minute", "hour", "day", "week", "month"),
        vol.Optional("units"): UNIT_SCHEMA,
        vol.Optional("types"): vol.All(
            [vol.Any("change", "last_reset", "max", "mean", "min", "state", "sum")],
            vol.Coerce(set),
        ),
    }
)
@websocket_api.async_response
async def ws_get_statistics_during_period(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle statistics websocket command."""
    await ws_handle_get_statistics_during_period(hass, connection, msg)


def _ws_get_list_statistic_ids(
    hass: HomeAssistant,
    msg_id: int,
    statistic_type: Literal["mean", "sum"] | None = None,
) -> bytes:
    """Fetch a list of available statistic_id and convert them to JSON.

    Runs in the executor.
    """
    return json_bytes(
        messages.result_message(msg_id, list_statistic_ids(hass, None, statistic_type))
    )


async def ws_handle_list_statistic_ids(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Fetch a list of available statistic_id."""
    connection.send_message(
        await get_instance(hass).async_add_executor_job(
            _ws_get_list_statistic_ids,
            hass,
            msg["id"],
            msg.get("statistic_type"),
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/list_statistic_ids",
        vol.Optional("statistic_type"): vol.Any("sum", "mean"),
    }
)
@websocket_api.async_response
async def ws_list_statistic_ids(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Fetch a list of available statistic_id."""
    await ws_handle_list_statistic_ids(hass, connection, msg)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/validate_statistics",
    }
)
@websocket_api.async_response
async def ws_validate_statistics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Validate statistics and return issues found."""
    instance = get_instance(hass)
    validation_issues = await instance.async_add_executor_job(
        validate_statistics,
        hass,
    )
    connection.send_result(msg["id"], validation_issues)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/update_statistics_issues",
    }
)
@websocket_api.async_response
async def ws_update_statistics_issues(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update statistics issues."""
    instance = get_instance(hass)
    await instance.async_add_executor_job(
        update_statistics_issues,
        hass,
    )
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/clear_statistics",
        vol.Required("statistic_ids"): [str],
    }
)
@websocket_api.async_response
async def ws_clear_statistics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Clear statistics for a list of statistic_ids.

    Note: The WS call posts a job to the recorder's queue and then returns, it doesn't
    wait until the job is completed.
    """
    done_event = asyncio.Event()

    def clear_statistics_done() -> None:
        hass.loop.call_soon_threadsafe(done_event.set)

    get_instance(hass).async_clear_statistics(
        msg["statistic_ids"], on_done=clear_statistics_done
    )
    try:
        async with asyncio.timeout(CLEAR_STATISTICS_TIME_OUT):
            await done_event.wait()
    except TimeoutError:
        connection.send_error(
            msg["id"], websocket_api.ERR_TIMEOUT, "clear_statistics timed out"
        )
        return

    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/get_statistics_metadata",
        vol.Optional("statistic_ids"): [str],
    }
)
@websocket_api.async_response
async def ws_get_statistics_metadata(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get metadata for a list of statistic_ids."""
    statistic_ids = msg.get("statistic_ids")
    statistic_ids_set_or_none = set(statistic_ids) if statistic_ids else None
    metadata = await async_list_statistic_ids(hass, statistic_ids_set_or_none)
    connection.send_result(msg["id"], metadata)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/update_statistics_metadata",
        vol.Required("statistic_id"): str,
        vol.Optional("unit_class"): vol.Any(str, None),
        vol.Required("unit_of_measurement"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_update_statistics_metadata(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update statistics metadata for a statistic_id.

    The unit_class specifies which unit conversion class to use, if applicable.

    Only the normalized unit of measurement can be updated.
    """
    done_event = asyncio.Event()

    def update_statistics_metadata_done() -> None:
        hass.loop.call_soon_threadsafe(done_event.set)

    if "unit_class" not in msg:
        _LOGGER.warning(
            "WS command recorder/update_statistics_metadata called without "
            "specifying unit_class in metadata, this is deprecated and will "
            "stop working in HA Core 2026.11"
        )

    async_update_statistics_metadata(
        hass,
        msg["statistic_id"],
        new_unit_class=msg.get("unit_class", UNDEFINED),
        new_unit_of_measurement=msg["unit_of_measurement"],
        on_done=update_statistics_metadata_done,
        _called_from_ws_api=True,
    )
    try:
        async with asyncio.timeout(UPDATE_STATISTICS_METADATA_TIME_OUT):
            await done_event.wait()
    except TimeoutError:
        connection.send_error(
            msg["id"], websocket_api.ERR_TIMEOUT, "update_statistics_metadata timed out"
        )
        return

    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/change_statistics_unit",
        vol.Required("statistic_id"): str,
        vol.Required("new_unit_of_measurement"): vol.Any(str, None),
        vol.Required("old_unit_of_measurement"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_change_statistics_unit(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Change the unit_of_measurement for a statistic_id.

    All existing statistics will be converted to the new unit.
    """
    await async_change_statistics_unit(
        hass,
        msg["statistic_id"],
        new_unit_of_measurement=msg["new_unit_of_measurement"],
        old_unit_of_measurement=msg["old_unit_of_measurement"],
    )
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/adjust_sum_statistics",
        vol.Required("statistic_id"): str,
        vol.Required("start_time"): str,
        vol.Required("adjustment"): vol.Any(float, int),
        vol.Required("adjustment_unit_of_measurement"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_adjust_sum_statistics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Adjust sum statistics.

    If the statistics is stored as NORMALIZED_UNIT,
    it's allowed to make an adjustment in VALID_UNIT
    """
    start_time_str = msg["start_time"]

    if start_time := dt_util.parse_datetime(start_time_str):
        start_time = dt_util.as_utc(start_time)
    else:
        connection.send_error(msg["id"], "invalid_start_time", "Invalid start time")
        return

    instance = get_instance(hass)
    metadatas = await instance.async_add_executor_job(
        list_statistic_ids, hass, {msg["statistic_id"]}
    )
    if not metadatas:
        connection.send_error(msg["id"], "unknown_statistic_id", "Unknown statistic ID")
        return
    metadata = metadatas[0]

    def valid_units(
        unit_class: str | None, statistics_unit: str | None, adjustment_unit: str | None
    ) -> bool:
        if statistics_unit == adjustment_unit:
            return True
        if (
            (converter := UNIT_CLASS_TO_UNIT_CONVERTER.get(unit_class)) is not None
            and statistics_unit in converter.VALID_UNITS
            and adjustment_unit in converter.VALID_UNITS
        ):
            return True
        return False

    unit_class = metadata["unit_class"]
    stat_unit = metadata["statistics_unit_of_measurement"]
    adjustment_unit = msg["adjustment_unit_of_measurement"]
    if not valid_units(unit_class, stat_unit, adjustment_unit):
        connection.send_error(
            msg["id"],
            "invalid_units",
            f"Can't convert {stat_unit} to {adjustment_unit}",
        )
        return

    get_instance(hass).async_adjust_statistics(
        msg["statistic_id"], start_time, msg["adjustment"], adjustment_unit
    )
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/import_statistics",
        vol.Required("metadata"): {
            vol.Optional("has_mean"): bool,
            vol.Optional("mean_type"): vol.All(
                vol.In(StatisticMeanType.__members__.values()),
                vol.Coerce(StatisticMeanType),
            ),
            vol.Required("has_sum"): bool,
            vol.Required("name"): vol.Any(str, None),
            vol.Required("source"): str,
            vol.Required("statistic_id"): str,
            vol.Optional("unit_class"): vol.Any(str, None),
            vol.Required("unit_of_measurement"): vol.Any(str, None),
        },
        vol.Required("stats"): [
            {
                vol.Required("start"): cv.datetime,
                vol.Optional("mean"): vol.Any(float, int),
                vol.Optional("min"): vol.Any(float, int),
                vol.Optional("max"): vol.Any(float, int),
                vol.Optional("last_reset"): vol.Any(cv.datetime, None),
                vol.Optional("state"): vol.Any(float, int),
                vol.Optional("sum"): vol.Any(float, int),
            }
        ],
    }
)
@callback
def ws_import_statistics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Import statistics.

    The unit_class specifies which unit conversion class to use, if applicable.
    """
    metadata = msg["metadata"]
    if "mean_type" not in metadata:
        _LOGGER.warning(
            "WS command recorder/import_statistics called without specifying "
            "mean_type in metadata, this is deprecated and will stop working "
            "in HA Core 2026.11"
        )
    if "unit_class" not in metadata:
        _LOGGER.warning(
            "WS command recorder/import_statistics called without specifying "
            "unit_class in metadata, this is deprecated and will stop working "
            "in HA Core 2026.11"
        )
    stats = msg["stats"]

    if valid_entity_id(metadata["statistic_id"]):
        async_import_statistics(hass, metadata, stats, _called_from_ws_api=True)
    else:
        async_add_external_statistics(hass, metadata, stats, _called_from_ws_api=True)
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/get_entity_exclusions",
    }
)
@callback
def ws_get_entity_exclusions(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get entity exclusions from both YAML config and storage.

    Returns a dict with entity_id -> source ("yaml" or "storage") mapping.
    """
    instance = get_instance(hass)
    exclusions_store = instance.exclusions_store

    if exclusions_store is None:
        connection.send_result(msg["id"], {"exclusions": {}})
        return

    # Get storage exclusions with source info
    result = exclusions_store.get_exclusions_data()

    connection.send_result(
        msg["id"],
        {
            "exclusions": result,
            "storage_exclusions": sorted(exclusions_store.excluded_entities),
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/update_entity_exclusions",
        vol.Optional("add"): vol.All([str], vol.Length(min=1)),
        vol.Optional("remove"): vol.All([str], vol.Length(min=1)),
    }
)
@websocket_api.async_response
async def ws_update_entity_exclusions(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Update entity exclusions in storage.

    Allows adding and/or removing entities from the exclusion list.
    Changes are persisted and take effect immediately.
    """
    instance = get_instance(hass)
    exclusions_store = instance.exclusions_store

    if exclusions_store is None:
        connection.send_error(
            msg["id"],
            "not_initialized",
            "Exclusions store not initialized",
        )
        return

    add_entities = msg.get("add", [])
    remove_entities = msg.get("remove", [])

    if not add_entities and not remove_entities:
        connection.send_error(
            msg["id"],
            "invalid_request",
            "Must specify at least one entity to add or remove",
        )
        return

    # Validate entity IDs
    invalid_entities = [
        entity_id
        for entity_id in add_entities + remove_entities
        if not valid_entity_id(entity_id)
    ]

    if invalid_entities:
        connection.send_error(
            msg["id"],
            "invalid_entity_id",
            f"Invalid entity IDs: {', '.join(invalid_entities)}",
        )
        return

    # Check for non-existent entities (warning only)
    entity_states = hass.states
    warnings = [
        f"Entity '{entity_id}' does not exist"
        for entity_id in add_entities
        if entity_states.get(entity_id) is None
    ]

    # Apply changes - using loops since methods have side effects
    added = [
        entity_id
        for entity_id in add_entities
        if exclusions_store.add_exclusion(entity_id)
    ]
    removed = [
        entity_id
        for entity_id in remove_entities
        if exclusions_store.remove_exclusion(entity_id)
    ]

    # Persist changes
    if added or removed:
        await exclusions_store.async_save()

    connection.send_result(
        msg["id"],
        {
            "added": added,
            "removed": removed,
            "warnings": warnings,
            "current_exclusions": sorted(exclusions_store.excluded_entities),
        },
    )
