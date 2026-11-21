"""Tests for SNMP utility methods."""

import pysnmp.hlapi.v3arch.asyncio as hlapi
from pysnmp.hlapi.v3arch.asyncio import UsmUserData
import pytest

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


@pytest.mark.parametrize(
    ("data", "expected_auth_protocol", "expected_priv_protocol"),
    [
        pytest.param(
            {CONF_USERNAME: "test_user"},
            hlapi.usmNoAuthProtocol,
            hlapi.usmNoPrivProtocol,
            id="no_keys",
        ),
        pytest.param(
            {CONF_USERNAME: "test_user", CONF_AUTH_KEY: "test_auth_key"},
            hlapi.usmNoAuthProtocol,
            hlapi.usmNoPrivProtocol,
            id="auth_key_without_protocol",
        ),
        pytest.param(
            {CONF_USERNAME: "test_user", CONF_AUTH_PROTOCOL: "hmac-md5"},
            hlapi.usmNoAuthProtocol,
            hlapi.usmNoPrivProtocol,
            id="auth_protocol_without_key",
        ),
        pytest.param(
            {
                CONF_USERNAME: "test_user",
                CONF_AUTH_KEY: "test_auth_key",
                CONF_AUTH_PROTOCOL: "hmac-md5",
            },
            hlapi.usmHMACMD5AuthProtocol,
            hlapi.usmNoPrivProtocol,
            id="authentication_without_privacy",
        ),
        pytest.param(
            {CONF_USERNAME: "test_user", CONF_PRIV_PROTOCOL: "aes-cfb-128"},
            hlapi.usmNoAuthProtocol,
            hlapi.usmNoPrivProtocol,
            id="priv_protocol_without_key",
        ),
        pytest.param(
            {
                CONF_USERNAME: "test_user",
                CONF_AUTH_KEY: "test_auth_key",
                CONF_AUTH_PROTOCOL: "hmac-md5",
                CONF_PRIV_KEY: "test_priv_key",
                CONF_PRIV_PROTOCOL: "aes-cfb-128",
            },
            hlapi.usmHMACMD5AuthProtocol,
            hlapi.usmAesCfb128Protocol,
            id="authentication_and_privacy",
        ),
    ],
)
def test_create_auth_data_v3_protocols_need_keys(
    data: dict[str, str],
    expected_auth_protocol: object,
    expected_priv_protocol: object,
) -> None:
    """Test that a protocol is only applied together with its key."""
    auth_data = create_auth_data(data, "3")

    assert isinstance(auth_data, UsmUserData)
    assert auth_data.authProtocol == expected_auth_protocol
    assert auth_data.privProtocol == expected_priv_protocol
