"""The Recorder websocket API."""

import asyncio
from datetime import datetime as dt
import logging
from typing import Any, Literal, cast

import probatio

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
    FrequencyConverter,
    InformationConverter,
    MassConverter,
    MassVolumeConcentrationConverter,
    NitrogenDioxideConcentrationConverter,
    NitrogenMonoxideConcentrationConverter,
    OzoneConcentrationConverter,
    PowerConverter,
    PressureConverter,
    RadiationConcentrationConverter,
    ReactiveEnergyConverter,
    ReactivePowerConverter,
    SpeedConverter,
    SulphurDioxideConcentrationConverter,
    TemperatureConverter,
    TemperatureDeltaConverter,
    UnitlessRatioConverter,
    VolumeConverter,
    VolumeFlowRateConverter,
)

from .models import StatisticMeanType, StatisticPeriod
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
from .util import PERIOD_SCHEMA, get_instance, resolve_period

_LOGGER = logging.getLogger(__name__)

CLEAR_STATISTICS_TIME_OUT = 10
UPDATE_STATISTICS_METADATA_TIME_OUT = 10

UNIT_SCHEMA = probatio.Schema(
    {
        probatio.Optional("apparent_power"): probatio.In(
            ApparentPowerConverter.VALID_UNITS
        ),
        probatio.Optional("area"): probatio.In(AreaConverter.VALID_UNITS),
        probatio.Optional("blood_glucose_concentration"): probatio.In(
            BloodGlucoseConcentrationConverter.VALID_UNITS
        ),
        probatio.Optional("carbon_monoxide"): probatio.In(
            CarbonMonoxideConcentrationConverter.VALID_UNITS
        ),
        probatio.Optional("concentration"): probatio.In(
            MassVolumeConcentrationConverter.VALID_UNITS
        ),
        probatio.Optional("conductivity"): probatio.In(
            ConductivityConverter.VALID_UNITS
        ),
        probatio.Optional("data_rate"): probatio.In(DataRateConverter.VALID_UNITS),
        probatio.Optional("distance"): probatio.In(DistanceConverter.VALID_UNITS),
        probatio.Optional("duration"): probatio.In(DurationConverter.VALID_UNITS),
        probatio.Optional("electric_current"): probatio.In(
            ElectricCurrentConverter.VALID_UNITS
        ),
        probatio.Optional("energy"): probatio.In(EnergyConverter.VALID_UNITS),
        probatio.Optional("energy_distance"): probatio.In(
            EnergyDistanceConverter.VALID_UNITS
        ),
        probatio.Optional("frequency"): probatio.In(FrequencyConverter.VALID_UNITS),
        probatio.Optional("information"): probatio.In(InformationConverter.VALID_UNITS),
        probatio.Optional("mass"): probatio.In(MassConverter.VALID_UNITS),
        probatio.Optional("nitrogen_dioxide"): probatio.In(
            NitrogenDioxideConcentrationConverter.VALID_UNITS
        ),
        probatio.Optional("nitrogen_monoxide"): probatio.In(
            NitrogenMonoxideConcentrationConverter.VALID_UNITS
        ),
        probatio.Optional("ozone"): probatio.In(
            OzoneConcentrationConverter.VALID_UNITS
        ),
        probatio.Optional("power"): probatio.In(PowerConverter.VALID_UNITS),
        probatio.Optional("pressure"): probatio.In(PressureConverter.VALID_UNITS),
        probatio.Optional("radiation_concentration"): probatio.In(
            RadiationConcentrationConverter.VALID_UNITS
        ),
        probatio.Optional("reactive_energy"): probatio.In(
            ReactiveEnergyConverter.VALID_UNITS
        ),
        probatio.Optional("reactive_power"): probatio.In(
            ReactivePowerConverter.VALID_UNITS
        ),
        probatio.Optional("speed"): probatio.In(SpeedConverter.VALID_UNITS),
        probatio.Optional("sulphur_dioxide"): probatio.In(
            SulphurDioxideConcentrationConverter.VALID_UNITS
        ),
        probatio.Optional("temperature"): probatio.In(TemperatureConverter.VALID_UNITS),
        probatio.Optional("temperature_delta"): probatio.In(
            TemperatureDeltaConverter.VALID_UNITS
        ),
        probatio.Optional("unitless"): probatio.In(UnitlessRatioConverter.VALID_UNITS),
        probatio.Optional("voltage"): probatio.In(
            ElectricPotentialConverter.VALID_UNITS
        ),
        probatio.Optional("volume"): probatio.In(VolumeConverter.VALID_UNITS),
        probatio.Optional("volume_flow_rate"): probatio.In(
            VolumeFlowRateConverter.VALID_UNITS
        ),
    }
)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorder websocket API."""
    websocket_api.async_register_command(hass, ws_adjust_sum_statistics)
    websocket_api.async_register_command(hass, ws_change_statistics_unit)
    websocket_api.async_register_command(hass, ws_clear_statistics)
    websocket_api.async_register_command(hass, ws_get_statistic_during_period)
    websocket_api.async_register_command(hass, ws_get_statistics_during_period)
    websocket_api.async_register_command(hass, ws_get_statistics_metadata)
    websocket_api.async_register_command(hass, ws_list_statistic_ids)
    websocket_api.async_register_command(hass, ws_import_statistics)
    websocket_api.async_register_command(hass, ws_update_statistics_issues)
    websocket_api.async_register_command(hass, ws_update_statistics_metadata)
    websocket_api.async_register_command(hass, ws_validate_statistics)


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
        probatio.Required("type"): "recorder/statistic_during_period",
        probatio.Required("statistic_id"): str,
        probatio.Optional("types"): probatio.All(
            [probatio.Any("max", "mean", "min", "change")], probatio.Coerce(set)
        ),
        probatio.Optional("units"): UNIT_SCHEMA,
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
    period: Literal["5minute", "day", "hour", "week", "month", "year"],
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
        probatio.Required("type"): "recorder/statistics_during_period",
        probatio.Required("start_time"): str,
        probatio.Optional("end_time"): str,
        probatio.Required("statistic_ids"): probatio.All([str], probatio.Length(min=1)),
        probatio.Required("period"): probatio.Any(
            "5minute", "hour", "day", "week", "month", "year"
        ),
        probatio.Optional("units"): UNIT_SCHEMA,
        probatio.Optional("types"): probatio.All(
            [
                probatio.Any(
                    "change", "last_reset", "max", "mean", "min", "state", "sum"
                )
            ],
            probatio.Coerce(set),
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
        probatio.Required("type"): "recorder/list_statistic_ids",
        probatio.Optional("statistic_type"): probatio.Any("sum", "mean"),
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
        probatio.Required("type"): "recorder/validate_statistics",
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
        probatio.Required("type"): "recorder/update_statistics_issues",
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
        probatio.Required("type"): "recorder/clear_statistics",
        probatio.Required("statistic_ids"): [str],
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
        probatio.Required("type"): "recorder/get_statistics_metadata",
        probatio.Optional("statistic_ids"): [str],
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
        probatio.Required("type"): "recorder/update_statistics_metadata",
        probatio.Required("statistic_id"): str,
        probatio.Optional("unit_class"): probatio.Any(str, None),
        probatio.Required("unit_of_measurement"): probatio.Any(str, None),
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
        probatio.Required("type"): "recorder/change_statistics_unit",
        probatio.Required("statistic_id"): str,
        probatio.Required("new_unit_of_measurement"): probatio.Any(str, None),
        probatio.Required("old_unit_of_measurement"): probatio.Any(str, None),
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
        probatio.Required("type"): "recorder/adjust_sum_statistics",
        probatio.Required("statistic_id"): str,
        probatio.Required("start_time"): str,
        probatio.Required("adjustment"): probatio.Any(int, float),
        probatio.Required("adjustment_unit_of_measurement"): probatio.Any(str, None),
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
        probatio.Required("type"): "recorder/import_statistics",
        probatio.Required("metadata"): {
            probatio.Optional("has_mean"): bool,
            probatio.Optional("mean_type"): probatio.All(
                probatio.In(StatisticMeanType.__members__.values()),
                probatio.Coerce(StatisticMeanType),
            ),
            probatio.Required("has_sum"): bool,
            probatio.Required("name"): probatio.Any(str, None),
            probatio.Required("source"): str,
            probatio.Required("statistic_id"): str,
            probatio.Optional("unit_class"): probatio.Any(str, None),
            probatio.Required("unit_of_measurement"): probatio.Any(str, None),
        },
        probatio.Required("stats"): [
            {
                probatio.Required("start"): cv.datetime,
                probatio.Optional("mean"): probatio.Any(int, float),
                probatio.Optional("min"): probatio.Any(int, float),
                probatio.Optional("max"): probatio.Any(int, float),
                probatio.Optional("last_reset"): probatio.Any(cv.datetime, None),
                probatio.Optional("state"): probatio.Any(int, float),
                probatio.Optional("sum"): probatio.Any(int, float),
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
