"""Diagnostics support for InfluxDB."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import InfluxDBConfigEntry
from .const import CONF_ORG

TO_REDACT = {CONF_ORG, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: InfluxDBConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    influx_thread = entry.runtime_data
    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "writer": {
            "running": influx_thread.is_alive(),
            "queued_events": influx_thread.queue.qsize(),
            "max_retries": influx_thread.max_tries,
            "write_errors": influx_thread.write_errors,
        },
    }
