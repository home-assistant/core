"""Diagnostics support for discovergy."""
from __future__ import annotations

from typing import Any

from pydiscovergy.models import Meter

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from ...helpers.update_coordinator import DataUpdateCoordinator
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_SECRET,
    CONF_CONSUMER_KEY,
    CONF_CONSUMER_SECRET,
    COORDINATORS,
    DOMAIN,
    METERS,
)

TO_REDACT_CONFIG_ENTRY = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_SECRET,
    CONF_CONSUMER_KEY,
    CONF_CONSUMER_SECRET,
}

TO_REDACT_METER = {
    "serial_number",
    "full_serial_number",
    "location",
    "fullSerialNumber",
    "printedFullSerialNumber",
    "administrationNumber",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    flattened_meter: list[dict] = []
    last_readings: dict[str, dict] = {}
    meters: list[Meter] = hass.data[DOMAIN][entry.entry_id][METERS]

    if len(meters) > 0:
        for meter in meters:
            # make dict of meter data and redact some data
            flattened_meter.append(async_redact_data(meter.__dict__, TO_REDACT_METER))

            # get last reading for meter and make dict it
            coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
                COORDINATORS
            ][meter.get_meter_id()]
            last_readings[meter.get_meter_id()] = coordinator.data.__dict__

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT_CONFIG_ENTRY),
        "meters": flattened_meter,
        "readings": last_readings,
    }
