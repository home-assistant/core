"""Constants for uhoo tests."""

from typing import Any

from homeassistant.const import CONF_API_KEY

# Mock config data to be used across multiple tests
DOMAIN = "uhoo"
MOCK_CONFIG: dict = {CONF_API_KEY: "tes1232421232"}

MOCK_DEVICE: dict[str, Any] = {
    "deviceName": "Office Room",
    "serialNumber": "23f9239m92m3ffkkdkdd",
}

MOCK_DEVICE_DATA = [
    {
        "virusIndex": 3,
        "moldIndex": 4,
        "temperature": 28.9,
        "humidity": 67.6,
        "pm25": 9,
        "tvoc": 1,
        "co2": 771,
        "co": 0,
        "airPressure": 1008.2,
        "ozone": 5,
        "no2": 0,
        "timestamp": 1762946521,
    }
]
