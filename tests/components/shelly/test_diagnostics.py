"""Tests for Shelly diagnostics platform."""

from copy import deepcopy
from unittest.mock import ANY, Mock, PropertyMock

from aioshelly.ble.const import BLE_SCAN_RESULT_EVENT
from aioshelly.const import MODEL_25
from aioshelly.exceptions import DeviceConnectionError
import pytest

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.shelly.const import (
    CONF_BLE_SCANNER_MODE,
    DOMAIN,
    BLEScannerMode,
)
from homeassistant.components.shelly.diagnostics import TO_REDACT
from homeassistant.core import HomeAssistant

from . import init_integration, inject_rpc_device_event
from .conftest import MOCK_STATUS_COAP

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

RELAY_BLOCK_ID = 0


async def test_block_config_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_block_device: Mock
) -> None:
    """Test config entry diagnostics for block device."""
    await init_integration(hass, 1)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry_dict = entry.as_dict()
    entry_dict["data"].update(
        {key: REDACTED for key in TO_REDACT if key in entry_dict["data"]}
    )

    type(mock_block_device).last_error = PropertyMock(
        return_value=DeviceConnectionError()
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == {
        "entry": entry_dict | {"discovery_keys": {}},
        "bluetooth": "not initialized",
        "device_info": {
            "name": "Test name",
            "model": MODEL_25,
            "sw_version": "some fw string",
        },
        "device_settings": {"coiot": {"update_period": 15}},
        "device_status": MOCK_STATUS_COAP,
        "last_error": "DeviceConnectionError()",
    }


async def test_rpc_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test config entry diagnostics for rpc device."""
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "component": "script:1",
                    "data": [
                        1,
                        "aa:bb:cc:dd:ee:ff",
                        -62,
                        "AgEGCf9ZANH7O3TIkA==",
                        "EQcbxdWlAgC4n+YRTSIADaLLBhYADUgQYQ==",
                    ],
                    "event": BLE_SCAN_RESULT_EVENT,
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry_dict = entry.as_dict()
    entry_dict["data"].update(
        {key: REDACTED for key in TO_REDACT if key in entry_dict["data"]}
    )

    type(mock_rpc_device).last_error = PropertyMock(
        return_value=DeviceConnectionError()
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == {
        "entry": entry_dict | {"discovery_keys": {}},
        "bluetooth": {
            "scanner": {
                "connectable": False,
                "discovered_device_timestamps": {"AA:BB:CC:DD:EE:FF": ANY},
                "discovered_devices_and_advertisement_data": [
                    {
                        "address": "AA:BB:CC:DD:EE:FF",
                        "advertisement_data": [
                            None,
                            {
                                "89": {
                                    "__type": "<class 'bytes'>",
                                    "repr": "b'\\xd1\\xfb;t\\xc8\\x90'",
                                }
                            },
                            {
                                "00000d00-0000-1000-8000-00805f9b34fb": {
                                    "__type": "<class 'bytes'>",
                                    "repr": "b'H\\x10a'",
                                }
                            },
                            ["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
                            -127,
                            -62,
                            [],
                        ],
                        "details": {"source": "12:34:56:78:9A:BC"},
                        "name": None,
                        "rssi": -62,
                    }
                ],
                "last_detection": ANY,
                "monotonic_time": ANY,
                "name": "Mock Title (12:34:56:78:9A:BC)",
                "scanning": True,
                "start_time": ANY,
                "source": "12:34:56:78:9A:BC",
                "time_since_last_device_detection": {"AA:BB:CC:DD:EE:FF": ANY},
                "type": "ShellyBLEScanner",
            }
        },
        "device_info": {
            "name": "Test name",
            "model": MODEL_25,
            "sw_version": "some fw string",
        },
        "device_settings": {"ws_outbound_enabled": False},
        "device_status": {
            "sys": {
                "available_updates": {
                    "beta": {"version": "some_beta_version"},
                    "stable": {"version": "some_beta_version"},
                },
                "relay_in_thermostat": True,
            },
            "wifi": {"rssi": -63},
        },
        "last_error": "DeviceConnectionError()",
    }


@pytest.mark.parametrize(
    ("ws_outbound_server", "ws_outbound_server_valid"),
    [("ws://10.10.10.10:8123/api/shelly/ws", True), ("wrong_url", False)],
)
async def test_rpc_config_entry_diagnostics_ws_outbound(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    ws_outbound_server: str,
    ws_outbound_server_valid: bool,
) -> None:
    """Test config entry diagnostics for rpc device with websocket outbound."""
    config = deepcopy(mock_rpc_device.config)
    config["ws"] = {"enable": True, "server": ws_outbound_server}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    entry = await init_integration(hass, 2, sleep_period=60)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert (
        result["device_settings"]["ws_outbound_server_valid"]
        == ws_outbound_server_valid
    )
