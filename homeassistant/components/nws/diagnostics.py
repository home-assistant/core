"""Diagnostics support for NWS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import NWSConfigEntry
from .const import CONF_STATION

CONFIG_TO_REDACT = {CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_STATION}
OBSERVATION_TO_REDACT = {"station"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: NWSConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    nws_data = config_entry.runtime_data.api

    return {
        "info": async_redact_data(config_entry.data, CONFIG_TO_REDACT),
        "observation": async_redact_data(nws_data.observation, OBSERVATION_TO_REDACT),
        "forecast": nws_data.forecast,
        "forecast_hourly": nws_data.forecast_hourly,
    }
