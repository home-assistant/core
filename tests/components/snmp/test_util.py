"""Tests for SNMP utility methods."""

from unittest.mock import patch

from pysnmp.error import PySnmpError
import pysnmp.hlapi.v3arch.asyncio as hlapi
from pysnmp.hlapi.v3arch.asyncio import UsmUserData
import pytest

from homeassistant.components.snmp.const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_PRIV_KEY,
    CONF_PRIV_PROTOCOL,
)
from homeassistant.components.snmp.util import (
    async_create_transport_target,
    create_auth_data,
)
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant


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


async def test_async_create_transport_target_ipv4_success(
    hass: HomeAssistant,
) -> None:
    """Test IPv4 transport target creation succeeds."""
    with patch(
        "homeassistant.components.snmp.util.UdpTransportTarget.create",
        return_value="ipv4_target",
    ) as mock_create:
        result = await async_create_transport_target("192.168.1.1", 161, 5.0)
        assert result == "ipv4_target"
        mock_create.assert_called_once()


async def test_async_create_transport_target_ipv6_fallback(
    hass: HomeAssistant,
) -> None:
    """Test IPv6 fallback when IPv4 transport creation fails."""
    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        patch(
            "homeassistant.components.snmp.util.Udp6TransportTarget.create",
            return_value="ipv6_target",
        ) as mock_create6,
    ):
        result = await async_create_transport_target("::1", 161, 5.0)
        assert result == "ipv6_target"
        mock_create6.assert_called_once()


async def test_async_create_transport_target_all_fail(
    hass: HomeAssistant,
) -> None:
    """Test when both IPv4 and IPv6 transport creation fail."""
    with (
        patch(
            "homeassistant.components.snmp.util.UdpTransportTarget.create",
            side_effect=PySnmpError,
        ),
        patch(
            "homeassistant.components.snmp.util.Udp6TransportTarget.create",
            side_effect=PySnmpError,
        ),
        pytest.raises(PySnmpError),
    ):
        await async_create_transport_target("::1", 161, 5.0)
