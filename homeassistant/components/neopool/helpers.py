"""Helper functions for the NeoPool integration."""

import datetime
from typing import Any

from neopool_modbus.decoders import decode_device_time, encode_device_time

from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util


def get_device_time(
    data: dict[str, Any], hass: HomeAssistant | None = None
) -> datetime.datetime | None:
    """Decode ``MBF_PAR_TIME`` as UTC-normalised wall-clock time."""
    unix_ts = data.get("MBF_PAR_TIME")
    if unix_ts is None:
        return None
    tz = (
        dt_util.get_time_zone(hass.config.time_zone) if hass else datetime.UTC
    ) or datetime.UTC
    return decode_device_time(unix_ts, tz)


def prepare_device_time(hass: HomeAssistant) -> int:
    """Return the unix timestamp the device should display as local wall-clock."""
    tz = dt_util.get_time_zone(hass.config.time_zone) or datetime.UTC
    return encode_device_time(dt_util.now(tz))


def is_device_time_out_of_sync(
    data: dict[str, Any], hass: HomeAssistant | None = None, threshold_seconds: int = 60
) -> bool:
    """Returns True if device time and HA time differ by more than threshold_seconds."""
    device_dt = get_device_time(data, hass)
    if device_dt is None:
        return False
    now_dt = dt_util.utcnow().replace(tzinfo=datetime.UTC)
    diff = abs((device_dt - now_dt).total_seconds())
    return diff > threshold_seconds
