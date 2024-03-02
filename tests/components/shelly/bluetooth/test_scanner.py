"""Test the shelly bluetooth scanner."""
from __future__ import annotations

from aioshelly.ble.const import BLE_SCAN_RESULT_EVENT
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.shelly.const import CONF_BLE_SCANNER_MODE, BLEScannerMode
from homeassistant.core import HomeAssistant

from .. import init_integration, inject_rpc_device_event


async def test_scanner_v1(hass: HomeAssistant, mock_rpc_device, monkeypatch) -> None:
    """Test injecting data into the scanner v1."""
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )
    assert mock_rpc_device.initialized is True
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
    ble_device = bluetooth.async_ble_device_from_address(
        hass, "AA:BB:CC:DD:EE:FF", connectable=False
    )
    assert ble_device is not None
    ble_device = bluetooth.async_ble_device_from_address(
        hass, "AA:BB:CC:DD:EE:FF", connectable=True
    )
    assert ble_device is None


async def test_scanner_v2(hass: HomeAssistant, mock_rpc_device, monkeypatch) -> None:
    """Test injecting data into the scanner v2."""
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )
    assert mock_rpc_device.initialized is True
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "component": "script:1",
                    "data": [
                        2,
                        [
                            [
                                "aa:bb:cc:dd:ee:ff",
                                -62,
                                "AgEGCf9ZANH7O3TIkA==",
                                "EQcbxdWlAgC4n+YRTSIADaLLBhYADUgQYQ==",
                            ]
                        ],
                    ],
                    "event": BLE_SCAN_RESULT_EVENT,
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    ble_device = bluetooth.async_ble_device_from_address(
        hass, "AA:BB:CC:DD:EE:FF", connectable=False
    )
    assert ble_device is not None
    ble_device = bluetooth.async_ble_device_from_address(
        hass, "AA:BB:CC:DD:EE:FF", connectable=True
    )
    assert ble_device is None


async def test_scanner_ignores_non_ble_events(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test injecting non ble data into the scanner."""
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )
    assert mock_rpc_device.initialized is True
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "component": "script:1",
                    "data": [],
                    "event": "not_ble_scan_result",
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )


async def test_scanner_ignores_wrong_version_and_logs(
    hass: HomeAssistant, mock_rpc_device, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test injecting wrong version of ble data into the scanner."""
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )
    assert mock_rpc_device.initialized is True
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "component": "script:1",
                    "data": [
                        0,
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
    assert "Unsupported BLE scan result version: 0" in caplog.text


async def test_scanner_warns_on_corrupt_event(
    hass: HomeAssistant, mock_rpc_device, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test injecting garbage ble data into the scanner."""
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )
    assert mock_rpc_device.initialized is True
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "component": "script:1",
                    "data": [
                        1,
                    ],
                    "event": BLE_SCAN_RESULT_EVENT,
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    assert "Failed to parse BLE event" in caplog.text
