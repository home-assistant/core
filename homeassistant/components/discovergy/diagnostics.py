"""Diagnostics support for discovergy."""
from __future__ import annotations

from typing import Any

from pydiscovergy.models import Meter

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from . import DiscovergyData
from .const import DOMAIN

TO_REDACT_CONFIG_ENTRY = {CONF_EMAIL, CONF_PASSWORD, CONF_UNIQUE_ID, "title"}

TO_REDACT_METER = {
    "serial_number",
    "full_serial_number",
    "location",
    "full_serial_number",
    "printed_full_serial_number",
    "administration_number",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    flattened_meter: list[dict] = []
    last_readings: dict[str, dict] = {}
    data: DiscovergyData = hass.data[DOMAIN][entry.entry_id]
    meters: list[Meter] = data.meters  # always returns a list

    for meter in meters:
        # make a dict of meter data and redact some data
        flattened_meter.append(async_redact_data(meter.__dict__, TO_REDACT_METER))

        # get last reading for meter and make a dict of it
        coordinator = data.coordinators[meter.meter_id]
        last_readings[meter.meter_id] = coordinator.data.__dict__

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT_CONFIG_ENTRY),
        "meters": flattened_meter,
        "readings": last_readings,
    }
