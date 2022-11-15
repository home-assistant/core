"""Test the shelly bluetooth scanner."""

from aioshelly.ble.const import BLE_SCAN_RESULT_EVENT

from .. import MOCK_MAC, init_integration, inject_rpc_device_event


async def test_scanner(hass, mock_rpc_device, monkeypatch):
    """Test injecting data into the scanner."""
    await init_integration(hass, 2)
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "component": "script:1",
                    "data": [
                        1,
                        MOCK_MAC,
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
