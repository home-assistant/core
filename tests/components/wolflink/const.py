"""Constants for the Wolf SmartSet Service tests."""

from homeassistant.components.wolflink.const import (
    DEVICE_GATEWAY,
    DEVICE_ID,
    DEVICE_NAME,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

CONFIG = {
    DEVICE_NAME: "test-device",
    DEVICE_ID: 1234,
    DEVICE_GATEWAY: 5678,
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}
