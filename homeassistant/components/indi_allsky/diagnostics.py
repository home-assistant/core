"""Diagnostics support for INDI Allsky."""

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import IndiAllSkyConfigEntry

TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IndiAllSkyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    client = coordinator.client

    exposure_dict: dict[str, Any] | None = None
    if coordinator.latest_exposure is not None:
        exposure_dict = dataclasses.asdict(coordinator.latest_exposure)

    keogram_dict: dict[str, Any] | None = None
    if coordinator.latest_keogram is not None:
        keogram_dict = dataclasses.asdict(coordinator.latest_keogram)

    startrail_dict: dict[str, Any] | None = None
    if coordinator.latest_startrail is not None:
        startrail_dict = dataclasses.asdict(coordinator.latest_startrail)

    sensor_dict: dict[str, Any] | None = None
    if coordinator.latest_sensor is not None:
        sensor_dict = dataclasses.asdict(coordinator.latest_sensor)

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": async_redact_data(entry.options, TO_REDACT),
        "connection": {
            "is_connected": client.is_connected,
            "is_control_connected": client.is_control_connected,
        },
        "coordinator_data": {
            "exposure": exposure_dict,
            "latest_keogram": keogram_dict,
            "latest_startrail": startrail_dict,
            "sensor": sensor_dict,
        },
    }
