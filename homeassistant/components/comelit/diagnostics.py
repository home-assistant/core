"""Diagnostics support for Comelit integration."""

from __future__ import annotations

from typing import Any

from aiocomelit import (
    ComelitSerialBridgeObject,
    ComelitVedoAreaObject,
    ComelitVedoZoneObject,
)
from aiocomelit.const import BRIDGE

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PIN, CONF_TYPE
from homeassistant.core import HomeAssistant

from .coordinator import ComelitConfigEntry

TO_REDACT = {CONF_PIN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ComelitConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data

    dev_list: list[dict[str, Any]] = []
    dev_type_list: list[dict[int, Any]] = []

    for dev_type in coordinator.data:
        dev_type_list = []
        for sensor_data in coordinator.data[dev_type].values():
            if isinstance(sensor_data, ComelitSerialBridgeObject):
                dev_type_list.append(
                    {
                        sensor_data.index: {
                            "name": sensor_data.name,
                            "status": sensor_data.status,
                            "human_status": sensor_data.human_status,
                            "protected": sensor_data.protected,
                            "val": sensor_data.val,
                            "zone": sensor_data.zone,
                            "power": sensor_data.power,
                            "power_unit": sensor_data.power_unit,
                        }
                    }
                )
            if isinstance(sensor_data, ComelitVedoAreaObject):
                dev_type_list.append(
                    {
                        sensor_data.index: {
                            "name": sensor_data.name,
                            "human_status": sensor_data.human_status.value,
                            "p1": sensor_data.p1,
                            "p2": sensor_data.p2,
                            "ready": sensor_data.ready,
                            "armed": sensor_data.armed,
                            "alarm": sensor_data.alarm,
                            "alarm_memory": sensor_data.alarm_memory,
                            "sabotage": sensor_data.sabotage,
                            "anomaly": sensor_data.anomaly,
                            "in_time": sensor_data.in_time,
                            "out_time": sensor_data.out_time,
                        }
                    }
                )
            if isinstance(sensor_data, ComelitVedoZoneObject):
                dev_type_list.append(
                    {
                        sensor_data.index: {
                            "name": sensor_data.name,
                            "human_status": sensor_data.human_status.value,
                            "status": sensor_data.status,
                            "status_api": sensor_data.status_api,
                        }
                    }
                )
        dev_list.append({dev_type: dev_type_list})

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "type": entry.data.get(CONF_TYPE, BRIDGE),
        "device_info": {
            "last_update success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception),
            "devices": dev_list,
        },
    }
