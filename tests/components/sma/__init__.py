"""Tests for the sma integration."""

import unittest
from unittest.mock import patch

from homeassistant.components.sma.const import CONF_GROUP
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
)

MOCK_DEVICE = {
    "manufacturer": "SMA",
    "name": "SMA Device Name",
    "type": "Sunny Boy 3.6",
    "serial": 123456789,
}

MOCK_USER_INPUT = {
    CONF_HOST: "1.1.1.1",
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
    CONF_GROUP: "user",
    CONF_PASSWORD: "password",
}

MOCK_DHCP_DISCOVERY_INPUT = {
    # CONF_HOST: "1.1.1.2",
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
    CONF_GROUP: "user",
    CONF_PASSWORD: "password",
}

MOCK_DHCP_DISCOVERY = {
    CONF_HOST: "1.1.1.1",
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
    CONF_GROUP: "user",
    CONF_PASSWORD: "password",
    CONF_MAC: "00:15:bb:00:ab:cd",
}


def _patch_async_setup_entry(return_value=True) -> unittest.mock._patch:
    """Patch async_setup_entry."""
    return patch(
        "homeassistant.components.sma.async_setup_entry",
        return_value=return_value,
    )
