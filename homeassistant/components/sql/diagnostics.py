"""Diagnostics support for SQL."""

from typing import Any

from sqlalchemy.engine import make_url

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components.recorder import CONF_DB_URL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .util import resolve_db_url

TO_REDACT = {CONF_DB_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    db_url = entry.data.get(CONF_DB_URL)
    return {
        "data": async_redact_data(entry.data, TO_REDACT),
        "options": dict(entry.options),
        "uses_recorder_db": db_url is None,
        # The driver name shows the SQL dialect without credentials or host
        "db_driver": make_url(resolve_db_url(hass, db_url)).drivername,
    }
