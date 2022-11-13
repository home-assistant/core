"""Bluetooth support for shelly."""

BLE_SCAN_RESULT_EVENT = "ble.scan_result"

BLE_SCRIPT_NAME = "homeassistant_ble_integration"

BLE_SCAN_RESULT_VERSION = 1

BLE_CODE = """
// Home Assistant %ha_version% BLE script
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
    duration_ms: -1,
    active: %active%,
    interval_ms: 320,
    window_ms: 30,
});
"""
