"""Helper functions for the NeoPool integration."""

import asyncio
import datetime
import logging
from typing import Any

from neopool_modbus import async_probe_serial
from neopool_modbus.exceptions import NeoPoolError
from neopool_modbus.registers import DEFAULT_MODBUS_FRAMER

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


def calculate_next_interval_time(
    seconds: float | None, hass: HomeAssistant | None = None
) -> datetime.datetime | None:
    """Return the timestamp for the next interval start, rounded to the nearest minute.

    Returns None if seconds is None, not a number, or <= 0.
    """
    if seconds is None or not isinstance(seconds, (int, float)) or seconds <= 0:
        return None

    if hass:
        ha_tz = dt_util.get_time_zone(hass.config.time_zone)
        now_local = dt_util.now(ha_tz)
        target_time = now_local + datetime.timedelta(seconds=seconds)
    else:
        now_utc = dt_util.utcnow()
        target_time = now_utc + datetime.timedelta(seconds=seconds)

    return target_time.replace(second=0, microsecond=0)


async def async_get_device_serial(
    config: dict[str, Any], timeout: float = 5.0
) -> str | None:
    """Perform minimal Modbus read to get device serial number."""
    host = config.get(CONF_HOST, "")
    port = config.get(CONF_PORT, 502)
    unit_id = config.get("unit_id", 1)
    framer = config.get("modbus_framer", DEFAULT_MODBUS_FRAMER)

    try:
        return await async_probe_serial(
            host,
            port=port,
            unit_id=unit_id,
            framer=framer,
            timeout=timeout,
        )
    except asyncio.CancelledError:
        raise
    except NeoPoolError as err:
        _LOGGER.warning(
            "Trial Modbus read failed for %s:%s: %s (%s)",
            host,
            port,
            err,
            type(err).__name__,
        )
        return None
