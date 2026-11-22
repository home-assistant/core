"""Diagnostics support for Raspberry Pi Power Supply Checker."""

from dataclasses import asdict
from typing import Any

from rpi_bad_power import UnderVoltage, UnderVoltageLegacy, UnderVoltageNew

from homeassistant.core import HomeAssistant

from . import RpiPowerConfigEntry


def _read_diagnostics(under_voltage: UnderVoltage) -> dict[str, Any]:
    """Read synchronous sysfs diagnostics in the executor thread."""
    data: dict[str, Any] = {
        "reader": type(under_voltage).__name__,
        "supports_push": under_voltage.supports_push,
    }
    if isinstance(under_voltage, UnderVoltageNew):
        data["sysfs_path"] = str(under_voltage.alarm_path)
    elif isinstance(under_voltage, UnderVoltageLegacy):
        data["sysfs_path"] = str(under_voltage.throttled_path)

    try:
        data["under_voltage"] = under_voltage.get()
    except OSError as err:
        data["under_voltage"] = None
        data["error"] = str(err)

    if isinstance(under_voltage, UnderVoltageLegacy):
        try:
            data["throttled_status"] = asdict(under_voltage.get_throttled_status())
        except OSError:
            data["throttled_status"] = None

    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RpiPowerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return await hass.async_add_executor_job(_read_diagnostics, entry.runtime_data)
