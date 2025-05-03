"""Support for recorder services."""

from __future__ import annotations

from datetime import timedelta
from typing import cast

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.helpers.service import (
    async_extract_entity_ids,
    async_register_admin_service,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .const import ATTR_APPLY_FILTER, ATTR_KEEP_DAYS, ATTR_REPACK, DOMAIN
from .core import Recorder
from .statistics import statistics_during_period
from .tasks import PurgeEntitiesTask, PurgeTask

SERVICE_PURGE = "purge"
SERVICE_PURGE_ENTITIES = "purge_entities"
SERVICE_ENABLE = "enable"
SERVICE_DISABLE = "disable"
SERVICE_GET_STATISTICS = "get_statistics"

SERVICE_PURGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_KEEP_DAYS): cv.positive_int,
        vol.Optional(ATTR_REPACK, default=False): cv.boolean,
        vol.Optional(ATTR_APPLY_FILTER, default=False): cv.boolean,
    }
)

ATTR_DOMAINS = "domains"
ATTR_ENTITY_GLOBS = "entity_globs"

SERVICE_PURGE_ENTITIES_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID, default=[]): cv.entity_ids,
            vol.Optional(ATTR_DOMAINS, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(ATTR_ENTITY_GLOBS, default=[]): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(ATTR_KEEP_DAYS, default=0): cv.positive_int,
        }
    ),
    vol.Any(
        vol.Schema({vol.Required(ATTR_ENTITY_ID): vol.IsTrue()}, extra=vol.ALLOW_EXTRA),
        vol.Schema({vol.Required(ATTR_DOMAINS): vol.IsTrue()}, extra=vol.ALLOW_EXTRA),
        vol.Schema(
            {vol.Required(ATTR_ENTITY_GLOBS): vol.IsTrue()}, extra=vol.ALLOW_EXTRA
        ),
        msg="At least one of entity_id, domains, or entity_globs must have a value",
    ),
)

SERVICE_ENABLE_SCHEMA = vol.Schema({})
SERVICE_DISABLE_SCHEMA = vol.Schema({})

SERVICE_GET_STATISTICS_SCHEMA = vol.Schema(
    {
        vol.Required("start_time"): cv.datetime,
        vol.Optional("end_time"): cv.datetime,
        vol.Optional("statistic_ids"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("period"): vol.In(["5minute", "hour", "day", "week", "month"]),
        vol.Optional("units"): vol.Schema({cv.string: cv.string}),
        vol.Optional("types"): vol.All(
            cv.ensure_list,
            [vol.In(["change", "last_reset", "max", "mean", "min", "state", "sum"])],
        ),
    }
)


@callback
def _async_register_purge_service(hass: HomeAssistant, instance: Recorder) -> None:
    async def async_handle_purge_service(service: ServiceCall) -> None:
        """Handle calls to the purge service."""
        kwargs = service.data
        keep_days = kwargs.get(ATTR_KEEP_DAYS, instance.keep_days)
        repack = cast(bool, kwargs[ATTR_REPACK])
        apply_filter = cast(bool, kwargs[ATTR_APPLY_FILTER])
        purge_before = dt_util.utcnow() - timedelta(days=keep_days)
        instance.queue_task(PurgeTask(purge_before, repack, apply_filter))

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_PURGE,
        async_handle_purge_service,
        schema=SERVICE_PURGE_SCHEMA,
    )


@callback
def _async_register_purge_entities_service(
    hass: HomeAssistant, instance: Recorder
) -> None:
    async def async_handle_purge_entities_service(service: ServiceCall) -> None:
        """Handle calls to the purge entities service."""
        entity_ids = await async_extract_entity_ids(hass, service)
        domains = service.data.get(ATTR_DOMAINS, [])
        keep_days = service.data.get(ATTR_KEEP_DAYS, 0)
        entity_globs = service.data.get(ATTR_ENTITY_GLOBS, [])
        entity_filter = generate_filter(domains, list(entity_ids), [], [], entity_globs)
        purge_before = dt_util.utcnow() - timedelta(days=keep_days)
        instance.queue_task(PurgeEntitiesTask(entity_filter, purge_before))

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_PURGE_ENTITIES,
        async_handle_purge_entities_service,
        schema=SERVICE_PURGE_ENTITIES_SCHEMA,
    )


@callback
def _async_register_enable_service(hass: HomeAssistant, instance: Recorder) -> None:
    async def async_handle_enable_service(service: ServiceCall) -> None:
        instance.set_enable(True)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ENABLE,
        async_handle_enable_service,
        schema=SERVICE_ENABLE_SCHEMA,
    )


@callback
def _async_register_disable_service(hass: HomeAssistant, instance: Recorder) -> None:
    async def async_handle_disable_service(service: ServiceCall) -> None:
        instance.set_enable(False)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_DISABLE,
        async_handle_disable_service,
        schema=SERVICE_DISABLE_SCHEMA,
    )


@callback
def _async_register_get_statistics_service(
    hass: HomeAssistant, instance: Recorder
) -> None:
    async def async_handle_get_statistics_service(
        service: ServiceCall,
    ) -> ServiceResponse:
        """Handle calls to the get_statistics service."""
        start_time = dt_util.as_utc(service.data["start_time"])
        end_time = (
            dt_util.as_utc(service.data["end_time"])
            if "end_time" in service.data
            else None
        )

        statistic_ids = service.data.get("statistic_ids")
        statistic_ids_set = set(statistic_ids) if statistic_ids else None

        period = service.data["period"]
        units = service.data.get("units")

        if (types := service.data.get("types")) is None:
            types = {"change", "last_reset", "max", "mean", "min", "state", "sum"}
        else:
            types = set(types)

        result = await instance.async_add_executor_job(
            statistics_during_period,
            hass,
            start_time,
            end_time,
            statistic_ids_set,
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
                if last_reset := row.get("last_reset") is not None:
                    formatted_row["last_reset"] = dt_util.utc_from_timestamp(
                        last_reset
                    ).isoformat()
                if state := row.get("state") is not None:
                    formatted_row["state"] = state
                if sum_value := row.get("sum") is not None:
                    formatted_row["sum"] = sum_value
                if min_value := row.get("min") is not None:
                    formatted_row["min"] = min_value
                if max_value := row.get("max") is not None:
                    formatted_row["max"] = max_value
                if mean := row.get("mean") is not None:
                    formatted_row["mean"] = mean
                if mean_weight := row.get("mean_weight") is not None:
                    formatted_row["mean_weight"] = mean_weight
                if change := row.get("change") is not None:
                    formatted_row["change"] = change

                formatted_statistic_rows.append(formatted_row)

            formatted_result[statistic_id] = formatted_statistic_rows

        return {"statistics": formatted_result}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_STATISTICS,
        async_handle_get_statistics_service,
        schema=SERVICE_GET_STATISTICS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


@callback
def async_register_services(hass: HomeAssistant, instance: Recorder) -> None:
    """Register recorder services."""
    _async_register_purge_service(hass, instance)
    _async_register_purge_entities_service(hass, instance)
    _async_register_enable_service(hass, instance)
    _async_register_disable_service(hass, instance)
    _async_register_get_statistics_service(hass, instance)
