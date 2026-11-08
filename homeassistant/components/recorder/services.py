"""Support for recorder services."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import cast

import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    State,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.helpers.recorder import DATA_INSTANCE
from homeassistant.helpers.service import (
    async_extract_entity_ids,
    async_register_admin_service,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .const import DOMAIN
from .history import state_changes_during_period
from .statistics import statistics_during_period
from .tasks import PurgeEntitiesTask, PurgeTask


class RecorderService(StrEnum):
    """Store keys for recorder services."""

    DISABLE = "disable"
    ENABLE = "enable"
    GET_HISTORY = "get_history"
    GET_STATISTICS = "get_statistics"
    PURGE = "purge"
    PURGE_ENTITIES = "purge_entities"


class RecorderServiceArgument(StrEnum):
    """Store keys for recorder service arguments."""

    ALLOW_TRUNCATION = "allow_truncation"
    APPLY_FILTER = "apply_filter"
    DOMAINS = "domains"
    END_TIME = "end_time"
    ENTITY_GLOBS = "entity_globs"
    KEEP_DAYS = "keep_days"
    PERIOD = "period"
    REPACK = "repack"
    START_TIME = "start_time"
    STATISTIC_IDS = "statistic_ids"
    TYPES = "types"
    UNITS = "units"


SERVICE_PURGE_SCHEMA = probatio.Schema(
    {
        probatio.Optional(RecorderServiceArgument.KEEP_DAYS): cv.positive_int,
        probatio.Optional(RecorderServiceArgument.REPACK, default=False): cv.boolean,
        probatio.Optional(
            RecorderServiceArgument.APPLY_FILTER, default=False
        ): cv.boolean,
    }
)

SERVICE_PURGE_ENTITIES_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Optional(
                CommonServiceArgument.ENTITY_ID, default=[]
            ): cv.entity_ids,
            probatio.Optional(
                RecorderServiceArgument.DOMAINS, default=[]
            ): probatio.All(probatio.EnsureList(), [cv.string]),
            probatio.Optional(
                RecorderServiceArgument.ENTITY_GLOBS, default=[]
            ): probatio.All(probatio.EnsureList(), [cv.string]),
            probatio.Optional(
                RecorderServiceArgument.KEEP_DAYS, default=0
            ): cv.positive_int,
        }
    ),
    probatio.Any(
        probatio.Schema(
            {probatio.Required(CommonServiceArgument.ENTITY_ID): probatio.IsTrue()},
            extra=probatio.ALLOW_EXTRA,
        ),
        probatio.Schema(
            {probatio.Required(RecorderServiceArgument.DOMAINS): probatio.IsTrue()},
            extra=probatio.ALLOW_EXTRA,
        ),
        probatio.Schema(
            {
                probatio.Required(
                    RecorderServiceArgument.ENTITY_GLOBS
                ): probatio.IsTrue()
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        msg="At least one of entity_id, domains, or entity_globs must have a value",
    ),
)

SERVICE_ENABLE_SCHEMA = probatio.Schema({})
SERVICE_DISABLE_SCHEMA = probatio.Schema({})

SERVICE_GET_STATISTICS_SCHEMA = probatio.Schema(
    {
        probatio.Required(RecorderServiceArgument.START_TIME): cv.datetime,
        probatio.Optional(RecorderServiceArgument.END_TIME): cv.datetime,
        probatio.Required(RecorderServiceArgument.STATISTIC_IDS): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Required(RecorderServiceArgument.PERIOD): probatio.In(
            ["5minute", "hour", "day", "week", "month", "year"]
        ),
        probatio.Required(RecorderServiceArgument.TYPES): probatio.All(
            probatio.EnsureList(),
            [
                probatio.In(
                    ["change", "last_reset", "max", "mean", "min", "state", "sum"]
                )
            ],
        ),
        probatio.Optional(RecorderServiceArgument.UNITS): probatio.Schema(
            {cv.string: cv.string}
        ),
    }
)

SERVICE_GET_HISTORY_SCHEMA = probatio.Schema(
    {
        probatio.Required(RecorderServiceArgument.START_TIME): cv.datetime,
        probatio.Optional(RecorderServiceArgument.END_TIME): cv.datetime,
        probatio.Required(CommonServiceArgument.ENTITY_ID): cv.entity_ids,
        probatio.Optional(
            RecorderServiceArgument.ALLOW_TRUNCATION, default=False
        ): cv.boolean,
    }
)

MAX_GET_HISTORY_RECORDS_PER_ENTITY = 1000


async def _async_handle_purge_service(service: ServiceCall) -> None:
    """Handle calls to the purge service."""
    instance = service.hass.data[DATA_INSTANCE]
    kwargs = service.data
    keep_days = kwargs.get(RecorderServiceArgument.KEEP_DAYS, instance.keep_days)
    repack = cast(bool, kwargs[RecorderServiceArgument.REPACK])
    apply_filter = cast(bool, kwargs[RecorderServiceArgument.APPLY_FILTER])
    purge_before = dt_util.utcnow() - timedelta(days=keep_days)
    instance.queue_task(PurgeTask(purge_before, repack, apply_filter))


async def _async_handle_purge_entities_service(service: ServiceCall) -> None:
    """Handle calls to the purge entities service."""
    # Keep group entities as purge targets instead of expanding them to their members.
    entity_ids = await async_extract_entity_ids(service, expand_group=False)
    domains = service.data.get(RecorderServiceArgument.DOMAINS, [])
    keep_days = service.data.get(RecorderServiceArgument.KEEP_DAYS, 0)
    entity_globs = service.data.get(RecorderServiceArgument.ENTITY_GLOBS, [])
    entity_filter = generate_filter(domains, list(entity_ids), [], [], entity_globs)
    purge_before = dt_util.utcnow() - timedelta(days=keep_days)
    service.hass.data[DATA_INSTANCE].queue_task(
        PurgeEntitiesTask(entity_filter, purge_before)
    )


async def _async_handle_enable_service(service: ServiceCall) -> None:
    service.hass.data[DATA_INSTANCE].set_enable(True)


async def _async_handle_disable_service(service: ServiceCall) -> None:
    service.hass.data[DATA_INSTANCE].set_enable(False)


async def _async_handle_get_statistics_service(
    service: ServiceCall,
) -> ServiceResponse:
    """Handle calls to the get_statistics service."""
    hass = service.hass
    start_time = dt_util.as_utc(service.data[RecorderServiceArgument.START_TIME])
    end_time = (
        dt_util.as_utc(service.data[RecorderServiceArgument.END_TIME])
        if RecorderServiceArgument.END_TIME in service.data
        else None
    )

    statistic_ids = service.data[RecorderServiceArgument.STATISTIC_IDS]
    types = service.data[RecorderServiceArgument.TYPES]
    period = service.data[RecorderServiceArgument.PERIOD]
    units = service.data.get(RecorderServiceArgument.UNITS)

    result = await hass.data[DATA_INSTANCE].async_add_executor_job(
        statistics_during_period,
        hass,
        start_time,
        end_time,
        statistic_ids,
        period,
        units,
        types,
    )

    formatted_result: JsonObjectType = {}
    for statistic_id, statistic_rows in result.items():
        formatted_statistic_rows: JsonArrayType = []

        for row in statistic_rows:
            formatted_row: JsonObjectType = {
                "start": dt_util.utc_from_timestamp(row["start"]).isoformat(),
                "end": dt_util.utc_from_timestamp(row["end"]).isoformat(),
            }
            if (last_reset := row.get("last_reset")) is not None:
                formatted_row["last_reset"] = dt_util.utc_from_timestamp(
                    last_reset
                ).isoformat()
            if (state := row.get("state")) is not None:
                formatted_row["state"] = state
            if (sum_value := row.get("sum")) is not None:
                formatted_row["sum"] = sum_value
            if (min_value := row.get("min")) is not None:
                formatted_row["min"] = min_value
            if (max_value := row.get("max")) is not None:
                formatted_row["max"] = max_value
            if (mean := row.get("mean")) is not None:
                formatted_row["mean"] = mean
            if (change := row.get("change")) is not None:
                formatted_row["change"] = change

            formatted_statistic_rows.append(formatted_row)

        formatted_result[statistic_id] = formatted_statistic_rows

    return {"statistics": formatted_result}


def _get_history(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None,
    entity_ids: list[str],
) -> dict[str, list[State]]:
    """Fetch history states for entities in a single executor job."""
    result: dict[str, list[State]] = {}

    for entity_id in entity_ids:
        result.update(
            state_changes_during_period(
                hass,
                start_time,
                end_time,
                entity_id=entity_id,
                no_attributes=True,
                descending=False,
                # Request limit + 1 records to allow detection of SQL silently truncating the in-window states.
                limit=MAX_GET_HISTORY_RECORDS_PER_ENTITY + 1,
                include_start_time_state=True,
            )
        )

    return result


async def _async_handle_get_history_service(
    service: ServiceCall,
) -> ServiceResponse:
    """Handle calls to the get_history service."""
    hass = service.hass
    start_time = dt_util.as_utc(service.data[RecorderServiceArgument.START_TIME])
    end_time = (
        dt_util.as_utc(service.data[RecorderServiceArgument.END_TIME])
        if RecorderServiceArgument.END_TIME in service.data
        else None
    )

    now = dt_util.utcnow()
    if start_time > now:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="start_time_in_future",
        )

    if end_time and end_time < start_time:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="end_time_before_start_time",
        )

    entity_ids: list[str] = service.data[CommonServiceArgument.ENTITY_ID]
    allow_truncation: bool = service.data[RecorderServiceArgument.ALLOW_TRUNCATION]
    result = await hass.data[DATA_INSTANCE].async_add_executor_job(
        _get_history,
        hass,
        start_time,
        end_time,
        entity_ids,
    )

    formatted_result: JsonObjectType = {}
    for entity_id, history_states_with_dups in result.items():
        has_start_state = bool(
            history_states_with_dups
            and history_states_with_dups[0].last_updated_timestamp
            == start_time.timestamp()
        )
        in_window_count = len(history_states_with_dups) - (1 if has_start_state else 0)

        # Remove consecutive states that are the same, this can occur due to restarts
        history_states: list[State] = []
        for index, state in enumerate(history_states_with_dups):
            if index == 0:
                history_states.append(state)
                continue
            if history_states_with_dups[index - 1].state == state.state:
                continue
            history_states.append(state)

        is_truncated = (
            in_window_count == MAX_GET_HISTORY_RECORDS_PER_ENTITY + 1
            or len(history_states) > MAX_GET_HISTORY_RECORDS_PER_ENTITY
        )
        if is_truncated:
            if not allow_truncation:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="max_records_exceeded",
                    translation_placeholders={
                        "entity_id": entity_id,
                        "max_records": str(MAX_GET_HISTORY_RECORDS_PER_ENTITY),
                    },
                )
            history_states = history_states[: MAX_GET_HISTORY_RECORDS_PER_ENTITY + 1]

        formatted_history_states: JsonArrayType = []

        for index, state in enumerate(history_states):
            if index == len(history_states) - 1:
                if is_truncated:
                    continue
                end = min(end_time, now) if end_time else now
            else:
                end = dt_util.utc_from_timestamp(
                    history_states[index + 1].last_updated_timestamp
                )
            formatted_state: JsonObjectType = {
                "start": dt_util.utc_from_timestamp(
                    state.last_updated_timestamp
                ).isoformat(),
                "end": end.isoformat(),
                "state": state.state,
            }

            formatted_history_states.append(formatted_state)

        formatted_result[entity_id] = formatted_history_states

    return {"history": formatted_result}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register recorder services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        RecorderService.PURGE,
        _async_handle_purge_service,
        schema=SERVICE_PURGE_SCHEMA,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        RecorderService.PURGE_ENTITIES,
        _async_handle_purge_entities_service,
        schema=SERVICE_PURGE_ENTITIES_SCHEMA,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        RecorderService.ENABLE,
        _async_handle_enable_service,
        schema=SERVICE_ENABLE_SCHEMA,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        RecorderService.DISABLE,
        _async_handle_disable_service,
        schema=SERVICE_DISABLE_SCHEMA,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        RecorderService.GET_STATISTICS,
        _async_handle_get_statistics_service,
        schema=SERVICE_GET_STATISTICS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        RecorderService.GET_HISTORY,
        _async_handle_get_history_service,
        schema=SERVICE_GET_HISTORY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
