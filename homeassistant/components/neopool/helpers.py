"""Helper functions for the NeoPool integration."""

import datetime

from neopool_modbus.decoders import encode_device_time

from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util


def prepare_device_time(hass: HomeAssistant) -> int:
    """Return the unix timestamp the device should display as local wall-clock."""
    tz = dt_util.get_time_zone(hass.config.time_zone) or datetime.UTC
    return encode_device_time(dt_util.now(tz))
