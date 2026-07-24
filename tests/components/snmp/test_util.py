"""Tests for SNMP utility methods."""

import pysnmp.hlapi.v3arch.asyncio as hlapi
from pysnmp.hlapi.v3arch.asyncio import UsmUserData

from homeassistant.components.snmp.const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_PRIV_KEY,
    CONF_PRIV_PROTOCOL,
)
from homeassistant.components.snmp.util import create_auth_data
from homeassistant.const import CONF_USERNAME


def test_create_auth_data_v3() -> None:
    """Test create_auth_data returns protocol objects for SNMPv3."""
    data = {
        CONF_USERNAME: "test_user",
        CONF_AUTH_KEY: "test_auth_key",
        CONF_AUTH_PROTOCOL: "hmac-md5",
        CONF_PRIV_KEY: "test_priv_key",
        CONF_PRIV_PROTOCOL: "aes-cfb-128",
    }

    auth_data = create_auth_data(data, "3")

    assert isinstance(auth_data, UsmUserData)
    # Verify that authProtocol is the actual object, not a string
    assert auth_data.authProtocol == hlapi.usmHMACMD5AuthProtocol
    assert auth_data.privProtocol == hlapi.usmAesCfb128Protocol
    assert not isinstance(auth_data.authProtocol, str)
    assert not isinstance(auth_data.privProtocol, str)


def test_create_auth_data_v3_defaults() -> None:
    """Test create_auth_data handles defaults correctly."""
    data = {
        CONF_USERNAME: "test_user",
        # Missing auth_proto and priv_proto
    }

    auth_data = create_auth_data(data, "3")

    assert isinstance(auth_data, UsmUserData)
    assert auth_data.authProtocol == hlapi.usmNoAuthProtocol
    assert auth_data.privProtocol == hlapi.usmNoPrivProtocol
