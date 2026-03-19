"""Test issue #163382."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from tuya_sharing import CustomerDevice, DeviceFunction, DeviceStatusRange, Manager

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_dumps
from homeassistant.util import dt as dt_util

from . import MockDeviceListener, initialize_entry

from tests.common import MockConfigEntry

_DEVICE_DETAILS = {
    "endpoint": "https://apigw.tuyaeu.com",
    "mqtt_connected": True,
    "disabled_by": None,
    "disabled_polling": False,
    "name": "Doln\u00ed vchod - z\u00e1pad",
    "category": "sp",
    "product_id": "ehzbfjrau5lbph4o",
    "product_name": "",
    "online": True,
    "sub": False,
    "time_zone": "+01:00",
    "active_time": "2022-01-27T13:26:32+00:00",
    "create_time": "2022-01-27T13:26:32+00:00",
    "update_time": "2022-01-27T13:26:32+00:00",
    "function": {
        "basic_flip": {"type": "Boolean", "value": "{}"},
        "basic_osd": {"type": "Boolean", "value": "{}"},
        "sd_format": {"type": "Boolean", "value": "{}"},
        "wireless_lowpower": {
            "type": "Integer",
            "value": '{"unit":"","min":10,"max":30,"scale":1,"step":1}',
        },
        "wireless_awake": {"type": "Boolean", "value": "{}"},
        "pir_switch": {"type": "Enum", "value": '{"range":["0","1","2","3"]}'},
        "basic_anti_flicker": {"type": "Enum", "value": '{"range":["0","1","2"]}'},
        "ipc_work_mode": {"type": "Enum", "value": '{"range":["0","1"]}'},
    },
    "status_range": {
        "basic_flip": {"type": "Boolean", "value": "{}", "report_type": None},
        "basic_osd": {"type": "Boolean", "value": "{}", "report_type": None},
        "sd_storge": {"type": "String", "value": '{"maxlen":255}', "report_type": None},
        "sd_status": {
            "type": "Integer",
            "value": '{"unit":"","min":1,"max":5,"scale":1,"step":1}',
            "report_type": None,
        },
        "sd_format": {"type": "Boolean", "value": "{}", "report_type": None},
        "movement_detect_pic": {"type": "Raw", "value": "{}", "report_type": None},
        "sd_format_state": {
            "type": "Integer",
            "value": '{"unit":"","min":-20000,"max":20000,"scale":1,"step":1}',
            "report_type": None,
        },
        "doorbell_active": {
            "type": "String",
            "value": '{"maxlen":255}',
            "report_type": None,
        },
        "wireless_electricity": {
            "type": "Integer",
            "value": '{"unit":"","min":0,"max":100,"scale":1,"step":1}',
            "report_type": None,
        },
        "wireless_powermode": {
            "type": "Enum",
            "value": '{"range":["0","1"]}',
            "report_type": None,
        },
        "wireless_lowpower": {
            "type": "Integer",
            "value": '{"unit":"","min":10,"max":30,"scale":1,"step":1}',
            "report_type": None,
        },
        "wireless_awake": {"type": "Boolean", "value": "{}", "report_type": None},
        "pir_switch": {
            "type": "Enum",
            "value": '{"range":["0","1","2","3"]}',
            "report_type": None,
        },
        "doorbell_pic": {"type": "Raw", "value": "{}", "report_type": None},
        "alarm_message": {"type": "String", "value": "{}", "report_type": None},
        "basic_anti_flicker": {
            "type": "Enum",
            "value": '{"range":["0","1","2"]}',
            "report_type": None,
        },
        "ipc_work_mode": {
            "type": "Enum",
            "value": '{"range":["0","1"]}',
            "report_type": None,
        },
    },
    "status": {
        "basic_flip": False,
        "basic_osd": False,
        "sd_storge": "0|0|0",
        "sd_status": 5,
        "sd_format": "false",
        "movement_detect_pic": "**REDACTED**",
        "sd_format_state": 0,
        "doorbell_active": "",
        "wireless_electricity": 100,
        "wireless_powermode": "1",
        "wireless_lowpower": "10",
        "wireless_awake": "false",
        "pir_switch": "1",
        "doorbell_pic": "**REDACTED**",
        "alarm_message": "**REDACTED**",
        "basic_anti_flicker": "1",
        "ipc_work_mode": "0",
    },
    "set_up": True,
    "support_local": False,
    "local_strategy": {},
    "warnings": None,
}


async def _async_update_device(
    mock_listener: MockDeviceListener,
    device: CustomerDevice,
    updated_status_properties: list[str] | None,
    dp_timestamps: dict[str, int] | None,
) -> None:
    """Trigger dispatcher_send for device update and wait for entity tasks to complete."""
    mock_listener.update_device(device, updated_status_properties, dp_timestamps)
    await mock_listener.hass.async_block_till_done()


async def _async_mock_device_online(
    mock_listener: MockDeviceListener, device: CustomerDevice
) -> None:
    """Mock online event from the manager."""
    device.online = True
    await _async_update_device(mock_listener, device, None, None)


async def _async_mock_device_offline(
    mock_listener: MockDeviceListener, device: CustomerDevice
) -> None:
    """Mock offline event from the manager."""
    device.online = False
    await _async_update_device(mock_listener, device, None, None)


async def _async_mock_device_update(
    mock_listener: MockDeviceListener,
    device: CustomerDevice,
    updated_status_properties: dict[str, Any] | None = None,
    dp_timestamps: dict[str, int] | None = None,
) -> None:
    """Mock update device method."""
    if isinstance(updated_status_properties, list):
        updated_status_properties = {
            prop: device.status.get(prop) for prop in updated_status_properties
        }

    property_list: list[str] | None = None
    if updated_status_properties is not None:
        property_list = []
        for key, value in updated_status_properties.items():
            if key not in device.status:
                raise ValueError(
                    f"Property {key} not found in device status: {device.status}"
                )
            device.status[key] = value
            property_list.append(key)
    await _async_update_device(mock_listener, device, property_list, dp_timestamps)


def _create_device() -> CustomerDevice:
    """Create a CustomerDevice for testing."""
    details = _DEVICE_DETAILS
    mock_device_code = "sp_ehzbfjrau5lbph4o"
    device = MagicMock(spec=CustomerDevice)

    # Use reverse of the product_id for testing
    device.id = mock_device_code.replace("_", "")[::-1]

    device.name = details["name"]
    device.category = details["category"]
    device.product_id = details["product_id"]
    device.product_name = details["product_name"]
    device.online = details["online"]
    device.sub = details.get("sub")
    device.time_zone = details.get("time_zone")
    device.active_time = details.get("active_time")
    if device.active_time:
        device.active_time = int(dt_util.as_timestamp(device.active_time))
    device.create_time = details.get("create_time")
    if device.create_time:
        device.create_time = int(dt_util.as_timestamp(device.create_time))
    device.update_time = details.get("update_time")
    if device.update_time:
        device.update_time = int(dt_util.as_timestamp(device.update_time))
    device.support_local = details.get("support_local")
    device.local_strategy = details.get("local_strategy")
    device.mqtt_connected = details.get("mqtt_connected")

    device.function = {
        key: DeviceFunction(
            code=key,
            type=value["type"],
            values=(
                values
                if isinstance(values := value["value"], str)
                else json_dumps(values)
            ),
        )
        for key, value in details["function"].items()
    }
    device.status_range = {
        key: DeviceStatusRange(
            code=key,
            report_type=value.get("report_type"),
            type=value["type"],
            values=(
                values
                if isinstance(values := value["value"], str)
                else json_dumps(values)
            ),
        )
        for key, value in details["status_range"].items()
    }
    device.status = details["status"]
    for key, value in device.status.items():
        # Some devices do not provide a status_range for all status DPs
        # Others set the type as String in status_range and as Json in function
        if ((dp_type := device.status_range.get(key)) and dp_type.type == "Json") or (
            (dp_type := device.function.get(key)) and dp_type.type == "Json"
        ):
            device.status[key] = json_dumps(value)
        if value == "**REDACTED**":
            # It was redacted, which may cause issue with b64decode
            device.status[key] = ""
    return device


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.EVENT])
@pytest.mark.freeze_time("2024-01-01")
async def test_event(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_listener: MockDeviceListener,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure event is only triggered when device reports actual data."""
    mock_device = _create_device()
    entity_id = "event.dolni_vchod_zapad_doorbell_message"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Initial state is unknown
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Simulate an initial device update to generate events
    freezer.tick(10)
    await _async_mock_device_update(mock_listener, mock_device, mock_device.status)
    assert hass.states.get(entity_id).state == "2024-01-01T00:00:10.000+00:00"

    freezer.tick(10)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_offline(mock_listener, mock_device)
    await _async_mock_device_online(mock_listener, mock_device)
    await _async_mock_device_offline(mock_listener, mock_device)
    await _async_mock_device_online(mock_listener, mock_device)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_status"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_offline(mock_listener, mock_device)
    await _async_mock_device_online(mock_listener, mock_device)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_offline(mock_listener, mock_device)
    await _async_mock_device_online(mock_listener, mock_device)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_offline(mock_listener, mock_device)
    await _async_mock_device_online(mock_listener, mock_device)
    await _async_mock_device_update(mock_listener, mock_device, None, None)
    await _async_mock_device_update(mock_listener, mock_device, ["basic_osd"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["basic_flip"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["ipc_work_mode"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["pir_switch"], {})
    await _async_mock_device_update(mock_listener, mock_device, [], {})
    await _async_mock_device_update(
        mock_listener, mock_device, ["basic_anti_flicker"], {}
    )
    await _async_mock_device_update(mock_listener, mock_device, ["sd_format_state"], {})
    await _async_mock_device_update(mock_listener, mock_device, ["sd_storge"], {})
    await _async_mock_device_update(mock_listener, mock_device, None, None)

    assert hass.states.get(entity_id).state == "2024-01-01T00:00:10.000+00:00"
