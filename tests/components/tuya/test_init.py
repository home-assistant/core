"""Test Tuya initialization."""

from __future__ import annotations

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya import CustomManager
from homeassistant.components.tuya.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import DEVICE_MOCKS, initialize_entry

from tests.common import MockConfigEntry, async_load_json_object_fixture


async def test_device_registry(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: CustomerDevice,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate device registry snapshots for all devices, including unsupported ones."""

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    device_registry_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    # Ensure the device registry contains same amount as DEVICE_MOCKS
    assert len(device_registry_entries) == len(DEVICE_MOCKS)

    for device_registry_entry in device_registry_entries:
        assert device_registry_entry == snapshot(
            name=list(device_registry_entry.identifiers)[0][1]
        )

        # Ensure model is suffixed with "(unsupported)" when no entities are generated
        assert (" (unsupported)" in device_registry_entry.model) == (
            not er.async_entries_for_device(
                entity_registry,
                device_registry_entry.id,
                include_disabled_entities=True,
            )
        )


async def test_fixtures_valid(hass: HomeAssistant) -> None:
    """Ensure Tuya fixture files are valid."""
    # We want to ensure that the fixture files do not contain
    # `home_assistant`, `id`, or `terminal_id` keys.
    # These are provided by the Tuya diagnostics and should be removed
    # from the fixture.
    EXCLUDE_KEYS = ("home_assistant", "id", "terminal_id")

    for device_code in DEVICE_MOCKS:
        details = await async_load_json_object_fixture(
            hass, f"{device_code}.json", DOMAIN
        )
        for key in EXCLUDE_KEYS:
            assert key not in details, (
                f"Please remove data[`'{key}']` from {device_code}.json"
            )


async def test_manager_fix() -> None:
    """Test manager fix for Tuya SDK.

    See https://github.com/home-assistant/core/issues/151239

    dpId `101` is present in the status update but not in the local_strategy, causing
    all subsequent dpId (`3`, `15`, `5`, `9`) in the message to be ignored.
    """
    with patch("tuya_sharing.manager.CustomerTokenInfo"):
        manager = CustomManager("test", "test", "test", "test")

    device = CustomerDevice(
        support_local=True,
        local_strategy={
            3: {
                "value_convert": "default",
                "status_code": "humidity",
                "config_item": {
                    "statusFormat": '{"humidity":"$"}',
                    "valueDesc": '{"unit":"%","min":0,"max":100,"scale":0,"step":1}',
                    "valueType": "Integer",
                    "enumMappingMap": {},
                    "pid": "rknwi0ctbbghzgla",
                },
            },
            5: {
                "value_convert": "default",
                "status_code": "temp_current",
                "config_item": {
                    "statusFormat": '{"temp_current":"$"}',
                    "valueDesc": '{"unit":"℃","min":0,"max":1000,"scale":1,"step":1}',
                    "valueType": "Integer",
                    "enumMappingMap": {},
                    "pid": "rknwi0ctbbghzgla",
                },
            },
            9: {
                "value_convert": "default",
                "status_code": "temp_unit_convert",
                "config_item": {
                    "statusFormat": '{"temp_unit_convert":"$"}',
                    "valueDesc": '{"range":["c","f"]}',
                    "valueType": "Enum",
                    "enumMappingMap": {},
                    "pid": "rknwi0ctbbghzgla",
                },
            },
            15: {
                "value_convert": "default",
                "status_code": "battery_percentage",
                "config_item": {
                    "statusFormat": '{"battery_percentage":"$"}',
                    "valueDesc": '{"unit":"%","min":0,"max":100,"scale":0,"step":1}',
                    "valueType": "Integer",
                    "enumMappingMap": {},
                    "pid": "rknwi0ctbbghzgla",
                },
            },
        },
        status={
            "humidity": 321,
            "temp_current": 321,
            "temp_unit_convert": "f",
            "battery_percentage": 321,
        },
    )
    manager.device_map = {"bfe251cfa8882fae3cpvup": device}

    manager.on_message(
        {
            "protocol": 20,
            "data": {
                "bizCode": "online",
                "bizData": {"devId": "bfe251cfa8882fae3cpvup", "time": 1759226706159},
                "ts": 1759226706408,
            },
            "t": 1759226706408,
        }
    )
    manager.on_message(
        {
            "protocol": 4,
            "data": {
                "devId": "bfe251cfa8882fae3cpvup",
                "dataId": "2711cd0c-c215-48f4-b535-243640e3b5b3",
                "productKey": "rknwi0ctbbghzgla",
                "status": [
                    {"dpId": 101, "t": 1759226706567, "value": 456},
                    {"dpId": 3, "t": 1759226706567, "value": 87},
                    {"dpId": 15, "t": 1759226706567, "value": 40},
                    {"dpId": 5, "t": 1759226706567, "value": 76},
                    {"dpId": 9, "t": 1759226706567, "value": "c"},
                ],
            },
            "t": 1759226707104,
        }
    )
    assert device.status == {
        "humidity": 87,
        "temp_current": 76,
        "temp_unit_convert": "c",
        "battery_percentage": 40,
    }
