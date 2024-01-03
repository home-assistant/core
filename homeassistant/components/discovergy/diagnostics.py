"""Diagnostics support for discovergy."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import DiscovergyUpdateCoordinator

TO_REDACT_METER = {
    "serial_number",
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
    coordinators: list[DiscovergyUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id]

    for coordinator in coordinators:
        # make a dict of meter data and redact some data
        flattened_meter.append(
            async_redact_data(asdict(coordinator.meter), TO_REDACT_METER)
        )

        # get last reading for meter and make a dict of it
        last_readings[coordinator.meter.meter_id] = asdict(coordinator.data)

    return {
        "meters": flattened_meter,
        "readings": last_readings,
    }
