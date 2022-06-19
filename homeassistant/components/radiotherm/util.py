"""Utils for radiotherm."""
from __future__ import annotations

from radiotherm.thermostat import CommonThermostat

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


async def async_set_time(hass: HomeAssistant, device: CommonThermostat) -> None:
    """Sync time to the thermostat."""
    await hass.async_add_executor_job(_set_time, device)


def _set_time(device: CommonThermostat) -> None:
    """Set device time."""
    # Calling this clears any local temperature override and
    # reverts to the scheduled temperature.
    now = dt_util.now()
    device.time = {
        "day": now.weekday(),
        "hour": now.hour,
        "minute": now.minute,
    }
