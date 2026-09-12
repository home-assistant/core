"""Tests for the Synology SRM integration."""

from typing import Any

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

MOCK_CONFIG: dict[str, Any] = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
    CONF_PORT: 8001,
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
}

DEVICE_1: dict[str, Any] = {
    "mac": "AA:BB:CC:DD:EE:01",
    "hostname": "device-one",
    "ip_addr": "192.168.1.10",
    "band": "5G",
    "connection": "wireless",
    "is_baned": False,
    "is_parental_controled": False,
    "signalstrength": -52,
    "transferRXRate": 100,
    "transferTXRate": 200,
}

DEVICE_2: dict[str, Any] = {
    "mac": "AA:BB:CC:DD:EE:02",
    "hostname": "device-two",
    "ip_addr": "192.168.1.11",
}

DEVICE_SPARSE: dict[str, Any] = {
    "mac": "AA:BB:CC:DD:EE:03",
}
