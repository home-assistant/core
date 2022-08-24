"""Provide info to system health."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from homeassistant.components import system_health
from homeassistant.components.recorder.core import Recorder
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant, callback

from .. import get_instance
from ..const import SupportedDialect
from .mysql import db_size_bytes as mysql_db_size_bytes
from .postgresql import db_size_bytes as postgresql_db_size_bytes
from .sqlite import db_size_bytes as sqlite_db_size_bytes

DIALECT_TO_GET_SIZE = {
    SupportedDialect.SQLITE: sqlite_db_size_bytes,
    SupportedDialect.MYSQL: mysql_db_size_bytes,
    SupportedDialect.POSTGRESQL: postgresql_db_size_bytes,
}


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


def _get_db_stats(instance: Recorder, database_name: str) -> dict[str, Any]:
    """Get the stats about the database."""
    db_stats: dict[str, Any] = {}
    with session_scope(session=instance.get_session()) as session:
        if (
            (dialect_name := instance.dialect_name)
            and (get_size := DIALECT_TO_GET_SIZE.get(dialect_name))
            and (db_bytes := get_size(session, database_name))
        ):
            db_stats["estimated_db_size"] = f"{db_bytes/1024/1024:.2f} MiB"
    return db_stats


@callback
def _async_get_db_engine_info(instance: Recorder) -> dict[str, Any]:
    """Get database engine info."""
    db_engine_info: dict[str, Any] = {}
    if dialect_name := instance.dialect_name:
        db_engine_info["database_engine"] = dialect_name.value
    if engine_version := instance.engine_version:
        db_engine_info["database_version"] = str(engine_version)
    return db_engine_info


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    instance = get_instance(hass)

    run_history = instance.run_history
    database_name = urlparse(instance.db_url).path.lstrip("/")
    db_engine_info = _async_get_db_engine_info(instance)
    db_stats: dict[str, Any] = {}

    if instance.async_db_ready.done():
        db_stats = await instance.async_add_executor_job(
            _get_db_stats, instance, database_name
        )
        db_runs = {
            "oldest_recorder_run": run_history.first.start,
            "current_recorder_run": run_history.current.start,
        }
    return db_runs | db_stats | db_engine_info
