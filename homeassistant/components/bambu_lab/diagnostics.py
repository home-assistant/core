"""Diagnostics support for the Bambu Lab integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import BambuLabConfigEntry
from .const import CONF_ACCESS_CODE, CONF_SERIAL_NUMBER

# The name of a print job can tell what someone prints.
TO_REDACT = {CONF_ACCESS_CODE, CONF_HOST, CONF_SERIAL_NUMBER, "serial", "job_name"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BambuLabConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client = entry.runtime_data

    return async_redact_data(
        {
            "config_entry_data": entry.data,
            "available": client.available,
            "info": asdict(client.info),
            "state": asdict(client.state),
        },
        TO_REDACT,
    )
