"""Diagnostics support for the Ambient Weather Network integration."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import API_STATION_TYPE, SENSOR_DESCRIPTIONS
from .coordinator import AmbientNetworkConfigEntry

SENSOR_KEYS = {description.key for description in SENSOR_DESCRIPTIONS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AmbientNetworkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    last_measured = coordinator.last_measured

    # The MAC address, station name, location, and time zone of the station
    # are left out, as they are private. Of the other reported fields, only the
    # names are included, to show which fields the integration does not use.
    return {
        "last_update_success": coordinator.last_update_success,
        "station_type": data.get(API_STATION_TYPE),
        "last_measured": (
            dt_util.as_utc(last_measured).isoformat()
            if last_measured is not None
            else None
        ),
        "readings": {key: data[key] for key in sorted(SENSOR_KEYS & data.keys())},
        "other_fields": sorted(data.keys() - SENSOR_KEYS),
    }
