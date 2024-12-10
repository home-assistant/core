"""Constants for the Watergate tests."""

from watergate_local_api.models import DeviceState

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
    {"volume": 1.2, "duration": 100},
    DEFAULT_SERIAL_NUMBER,
)
