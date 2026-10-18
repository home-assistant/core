"""Diagnostics support for Broadlink."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import BROADLINK_DATA

TO_REDACT = {CONF_HOST, CONF_MAC}

DAY_ID_TO_NAME = {
    1: "monday",
    2: "tuesday",
    3: "wednesday",
    4: "thursday",
    5: "friday",
    6: "saturday",
    7: "sunday",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = hass.data[BROADLINK_DATA].devices[entry.entry_id]
    assert device.update_manager is not None
    coordinator = device.update_manager.coordinator
    diagnostics: dict[str, Any] = {
        "entry": async_redact_data(entry.data, TO_REDACT),
        "device": {
            "type": device.api.type,
            "devtype": device.api.devtype,
            "model": device.api.model,
            "manufacturer": device.api.manufacturer,
            "fw_version": device.fw_version,
            "available": device.available,
        },
        "data": coordinator.data,
    }

    if device.api.type == "HYS" and (data := coordinator.data):
        diagnostics["device_clock"] = {
            "time": f"{data['hour']:02d}:{data['min']:02d}:{data['sec']:02d}",
            "day_of_week": DAY_ID_TO_NAME.get(data["dayofweek"]),
            "local_time": dt_util.now().isoformat(),
        }

    return diagnostics
