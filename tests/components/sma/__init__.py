"""Tests for the sma integration."""

from unittest.mock import patch

MOCK_DEVICE = {
    "manufacturer": "SMA",
    "name": "SMA Device Name",
    "type": "Sunny Boy 3.6",
    "serial": 123456789,
}

MOCK_USER_INPUT = {
    "host": "1.1.1.1",
    "ssl": True,
    "verify_ssl": False,
    "group": "user",
    "password": "password",
}

MOCK_DHCP_DISCOVERY = {
    "host": "1.1.1.1",
    "ssl": True,
    "verify_ssl": False,
    "group": "user",
    "password": "password",
    "mac": "00:15:bb:00:ab:cd",
}


def _patch_async_setup_entry(return_value=True):
    return patch(
        "homeassistant.components.sma.async_setup_entry",
        return_value=return_value,
    )
