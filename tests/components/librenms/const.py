"""Constants for the LibreNMS integration tests."""

from aiolibrenms.devices.models import LibrenmsDeviceInfo
from aiolibrenms.system.models import LibrenmsSystemInfo

from homeassistant.components.librenms.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)

from tests.common import load_fixture

MOCK_USER_DATA = {
    CONF_URL: "https://librenms",
    CONF_API_KEY: "abcdef0123456789",
    CONF_VERIFY_SSL: True,
}

MOCK_CONFIG_ENTRY_DATA = {
    CONF_HOST: "librenms",
    CONF_API_KEY: "abcdef0123456789",
    CONF_PORT: 443,
    CONF_SSL: True,
    CONF_VERIFY_SSL: True,
}

MOCK_SYSTEM_DATA = LibrenmsSystemInfo.from_json(
    load_fixture("system_data.json", DOMAIN)
)

MOCK_DEVICES_DATA = [
    LibrenmsDeviceInfo.from_json(load_fixture("device_1.json", DOMAIN)),
    LibrenmsDeviceInfo.from_json(load_fixture("device_3.json", DOMAIN)),
    LibrenmsDeviceInfo.from_json(load_fixture("device_13.json", DOMAIN)),
    LibrenmsDeviceInfo.from_json(load_fixture("device_29.json", DOMAIN)),
]
