"""Diagnostics support for the AWS S3 integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import S3ConfigEntry
from .const import CONF_SECRET_ACCESS_KEY

TO_REDACT = {CONF_SECRET_ACCESS_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: S3ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
    }
