"""Constants for the Watergate tests."""

from watergate_local_api.models import DeviceState, NetworkingData, TelemetryData
from watergate_local_api.models.water_meter import WaterMeter

from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_WEBHOOK_ID

MOCK_WEBHOOK_ID = "webhook_id"

MOCK_CONFIG = {
    CONF_NAME: "Sonic",
    CONF_IP_ADDRESS: "http://localhost",
    CONF_WEBHOOK_ID: MOCK_WEBHOOK_ID,
}

DEFAULT_SERIAL_NUMBER = "a63182948ce2896a"

DEFAULT_DEVICE_STATE = DeviceState(
    "open",
    "on",
    True,
    True,
    "battery",
    "1.0.0",
    100,
    WaterMeter(1.2, 100),
    DEFAULT_SERIAL_NUMBER,
)

DEFAULT_NETWORKING_STATE = NetworkingData(
    True,
    True,
    "192.168.1.127",
    "192.168.1.1",
    "255.255.255.0",
    "Sonic",
    -50,
    2137,
    1910,
)

DEFAULT_TELEMETRY_STATE = TelemetryData(0.0, 100, 28.32, None, [])
