"""Provide info to system health."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm.session import Session
from yarl import URL

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .. import get_instance
from ..const import DIALECT_MYSQL, DIALECT_POSTGRESQL, DIALECT_SQLITE
from .mysql import db_size_query as mysql_db_size_query
from .postgresql import db_size_query as postgresql_db_size_query
from .sqlite import db_size_query as sqlite_db_size_query

DIALECT_TO_QUERY = {
    DIALECT_SQLITE: sqlite_db_size_query,
    DIALECT_MYSQL: mysql_db_size_query,
    DIALECT_POSTGRESQL: postgresql_db_size_query,
}


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


def _get_estimated_db_size(
    session_maker: Callable[[], Session], dialect: str, database_name: str
) -> str | None:
    """Get the estimated size of the database."""
    if query := DIALECT_TO_QUERY.get(dialect):
        return query(session_maker(), database_name)
    return None


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    instance = get_instance(hass)
    run_history = instance.run_history
    database_name = URL(instance.db_url).path.lstrip("/")
    estimated_db_size = await instance.async_add_executor_job(
        _get_estimated_db_size, instance.get_session, instance.dialect, database_name
    )
    health_data = {
        "oldest_recorder_run": run_history.first.start,
        "current_recorder_run": run_history.current.start,
    }
    if estimated_db_size:
        health_data["estimated_db_size"] = estimated_db_size
    return health_data
