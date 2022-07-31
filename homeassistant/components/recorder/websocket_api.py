"""The Recorder websocket API."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback, valid_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import MAX_QUEUE_BACKLOG
from .statistics import (
    async_add_external_statistics,
    async_import_statistics,
    list_statistic_ids,
    validate_statistics,
)
from .util import async_migration_in_progress, async_migration_is_live, get_instance

_LOGGER: logging.Logger = logging.getLogger(__package__)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorder websocket API."""
    websocket_api.async_register_command(hass, ws_validate_statistics)
    websocket_api.async_register_command(hass, ws_clear_statistics)
    websocket_api.async_register_command(hass, ws_get_statistics_metadata)
    websocket_api.async_register_command(hass, ws_update_statistics_metadata)
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_backup_start)
    websocket_api.async_register_command(hass, ws_backup_end)
    websocket_api.async_register_command(hass, ws_adjust_sum_statistics)
    websocket_api.async_register_command(hass, ws_import_statistics)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/validate_statistics",
    }
)
@websocket_api.async_response
async def ws_validate_statistics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Fetch a list of available statistic_id."""
    instance = get_instance(hass)
    statistic_ids = await instance.async_add_executor_job(
        validate_statistics,
        hass,
    )
    connection.send_result(msg["id"], statistic_ids)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/clear_statistics",
        vol.Required("statistic_ids"): [str],
    }
)
@callback
def ws_clear_statistics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Clear statistics for a list of statistic_ids.

    Note: The WS call posts a job to the recorder's queue and then returns, it doesn't
    wait until the job is completed.
    """
    get_instance(hass).async_clear_statistics(msg["statistic_ids"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/get_statistics_metadata",
        vol.Optional("statistic_ids"): [str],
    }
)
@websocket_api.async_response
async def ws_get_statistics_metadata(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Get metadata for a list of statistic_ids."""
    instance = get_instance(hass)
    statistic_ids = await instance.async_add_executor_job(
        list_statistic_ids, hass, msg.get("statistic_ids")
    )
    connection.send_result(msg["id"], statistic_ids)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/update_statistics_metadata",
        vol.Required("statistic_id"): str,
        vol.Required("unit_of_measurement"): vol.Any(str, None),
    }
)
@callback
def ws_update_statistics_metadata(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Update statistics metadata for a statistic_id."""
    get_instance(hass).async_update_statistics_metadata(
        msg["statistic_id"], new_unit_of_measurement=msg["unit_of_measurement"]
    )
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/adjust_sum_statistics",
        vol.Required("statistic_id"): str,
        vol.Required("start_time"): str,
        vol.Required("adjustment"): vol.Any(float, int),
    }
)
@callback
def ws_adjust_sum_statistics(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Adjust sum statistics."""
    start_time_str = msg["start_time"]

    if start_time := dt_util.parse_datetime(start_time_str):
        start_time = dt_util.as_utc(start_time)
    else:
        connection.send_error(msg["id"], "invalid_start_time", "Invalid start time")
        return

    get_instance(hass).async_adjust_statistics(
        msg["statistic_id"], start_time, msg["adjustment"]
    )
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/import_statistics",
        vol.Required("metadata"): {
            vol.Required("has_mean"): bool,
            vol.Required("has_sum"): bool,
            vol.Required("name"): vol.Any(str, None),
            vol.Required("source"): str,
            vol.Required("statistic_id"): str,
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
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Adjust sum statistics."""
    metadata = msg["metadata"]
    stats = msg["stats"]

    if valid_entity_id(metadata["statistic_id"]):
        async_import_statistics(hass, metadata, stats)
    else:
        async_add_external_statistics(hass, metadata, stats)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/info",
    }
)
@callback
def ws_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return status of the recorder."""
    instance = get_instance(hass)

    backlog = instance.backlog if instance else None
    migration_in_progress = async_migration_in_progress(hass)
    migration_is_live = async_migration_is_live(hass)
    recording = instance.recording if instance else False
    thread_alive = instance.is_alive() if instance else False

    recorder_info = {
        "backlog": backlog,
        "max_backlog": MAX_QUEUE_BACKLOG,
        "migration_in_progress": migration_in_progress,
        "migration_is_live": migration_is_live,
        "recording": recording,
        "thread_running": thread_alive,
    }
    connection.send_result(msg["id"], recorder_info)


@websocket_api.ws_require_user(only_supervisor=True)
@websocket_api.websocket_command({vol.Required("type"): "backup/start"})
@websocket_api.async_response
async def ws_backup_start(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Backup start notification."""

    _LOGGER.info("Backup start notification, locking database for writes")
    instance = get_instance(hass)
    try:
        await instance.lock_database()
    except TimeoutError as err:
        connection.send_error(msg["id"], "timeout_error", str(err))
        return
    connection.send_result(msg["id"])


@websocket_api.ws_require_user(only_supervisor=True)
@websocket_api.websocket_command({vol.Required("type"): "backup/end"})
@websocket_api.async_response
async def ws_backup_end(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Backup end notification."""

    instance = get_instance(hass)
    _LOGGER.info("Backup end notification, releasing write lock")
    if not instance.unlock_database():
        connection.send_error(
            msg["id"], "database_unlock_failed", "Failed to unlock database."
        )
    connection.send_result(msg["id"])
