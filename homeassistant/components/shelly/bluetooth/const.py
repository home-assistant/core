"""Bluetooth support for shelly."""

BLE_SCAN_RESULT_EVENT = "ble.scan_result"

BLE_SCRIPT_NAME = "homeassistant_ble_integration"

BLE_SCAN_RESULT_VERSION = 1

VAR_EVENT_TYPE = "%event_type%"
VAR_ACTIVE = "%active%"
VAR_VERSION = "%version%"
VAR_INTERVAL_MS = "%interval_ms%"
VAR_WINDOW_MS = "%window_ms%"
VAR_DURATION_MS = "%duration_ms%"

DEFAULT_INTERVAL_MS = 320
DEFAULT_WINDOW_MS = 30
DEFAULT_DURATION_MS = -1

BLE_CODE = """
// aioshelly BLE script 1.0
BLE.Scanner.Subscribe(function (ev, res) {
    if (ev === BLE.Scanner.SCAN_RESULT) {
        Shelly.emitEvent("%event_type%", [
            %version%,
            res.addr,
            res.rssi,
            btoa(res.advData),
            btoa(res.scanRsp)
        ]);
    }
});
BLE.Scanner.Start({
    duration_ms: %duration_ms%,
    active: %active%,
    interval_ms: %interval_ms%,
    window_ms: %window_ms%,
});
"""
