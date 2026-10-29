"""Diagnostics support for Broadlink."""

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import BROADLINK_DATA

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
    api = device.api
    update_manager = device.update_manager
    if TYPE_CHECKING:
        assert update_manager is not None
    diagnostics: dict[str, Any] = {
        "device": {
            "type": api.type,
            "devtype": api.devtype,
            "model": api.model,
            "manufacturer": api.manufacturer,
            "fw_version": device.fw_version,
            "timeout": entry.data[CONF_TIMEOUT],
            "is_locked": api.is_locked,
        },
        "available": device.available,
        "update_manager": type(update_manager).__name__,
        "data": update_manager.coordinator.data,
    }

    if (
        api.type == "HYS"
        and (data := update_manager.coordinator.data)
        and (last_update := update_manager.last_update)
    ):
        # Compare the device clock with the local time it was read at, as
        # the coordinator data may be a few polls old.
        diagnostics["device_clock"] = {
            "time": f"{data['hour']:02d}:{data['min']:02d}:{data['sec']:02d}",
            "day_of_week": DAY_ID_TO_NAME.get(data["dayofweek"]),
            "local_time_at_poll": dt_util.as_local(last_update).isoformat(),
        }

    return diagnostics
