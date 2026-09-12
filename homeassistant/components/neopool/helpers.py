"""Helper functions for the NeoPool integration."""

import datetime
from typing import Any

from neopool_modbus.decoders import encode_device_time

from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util


def prepare_device_time(hass: HomeAssistant) -> int:
    """Return the unix timestamp the device should display as local wall-clock."""
    tz = dt_util.get_time_zone(hass.config.time_zone) or datetime.UTC
    return encode_device_time(dt_util.now(tz))


def is_device_time_out_of_sync(
    data: dict[str, Any],
    hass: HomeAssistant,
    threshold_seconds: int = 300,
) -> bool:
    """Return whether the device/HA wall-clock drift exceeds threshold_seconds."""
    device_ts: int | None = data.get("MBF_PAR_TIME")
    if device_ts is None:
        return False
    return abs(device_ts - prepare_device_time(hass)) > threshold_seconds
