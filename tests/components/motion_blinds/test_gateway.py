"""Tests for Motion Gateway interface detection."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.motion_blinds.gateway import ConnectMotionGateway
from homeassistant.components.motion_blinds.const import DEFAULT_INTERFACE
from homeassistant.core import HomeAssistant


MOCK_ADAPTERS_DUAL_NIC = [
    {
        "ipv4": [{"address": "192.168.1.10"}],
        "enabled": True,
        "default": True,
    },
    {
        "ipv4": [{"address": "192.168.20.10"}],
        "enabled": True,
        "default": False,
    },
]

MOCK_ADAPTERS_SINGLE_NIC = [
    {
        "ipv4": [{"address": "192.168.1.10"}],
        "enabled": True,
        "default": True,
    },
]


async def test_get_interfaces_dual_nic_default_prioritized(hass: HomeAssistant) -> None:
    """Test that default interface is first in list with multiple NICs."""
    gateway = ConnectMotionGateway(hass)

    with patch(
        "homeassistant.components.motion_blinds.gateway.network.async_get_adapters",
        return_value=MOCK_ADAPTERS_DUAL_NIC,
    ):
        interfaces = await gateway.async_get_interfaces()

    assert interfaces[0] == "192.168.1.10"


async def test_get_interfaces_single_nic(hass: HomeAssistant) -> None:
    """Test that single NIC setup still works correctly."""
    gateway = ConnectMotionGateway(hass)

    with patch(
        "homeassistant.components.motion_blinds.gateway.network.async_get_adapters",
        return_value=MOCK_ADAPTERS_SINGLE_NIC,
    ):
        interfaces = await gateway.async_get_interfaces()

    assert interfaces[0] == "192.168.1.10"


async def test_check_interface_timeout_moves_to_next(hass: HomeAssistant) -> None:
    """Test that a timed out interface check moves to the next interface."""
    gateway = ConnectMotionGateway(hass)
    successful_interface = "192.168.1.10"

    with patch(
        "homeassistant.components.motion_blinds.gateway.network.async_get_adapters",
        return_value=MOCK_ADAPTERS_DUAL_NIC,
    ), patch(
        "homeassistant.components.motion_blinds.gateway.AsyncMotionMulticast"
    ) as mock_multicast, patch(
        "homeassistant.components.motion_blinds.gateway.MotionGateway"
    ):
        mock_instance = MagicMock()
        mock_instance.Start_listen = AsyncMock()
        mock_instance.Stop_listen = MagicMock()
        mock_multicast.return_value = mock_instance

        call_count = 0

        def check_side_effect():
            nonlocal call_count
            call_count += 1
            return call_count > 1

        with patch.object(gateway, "check_interface", side_effect=check_side_effect):
            result = await gateway.async_check_interface("192.168.1.1", "testkey")

    assert result == successful_interface


async def test_check_interface_found_on_first_try(hass: HomeAssistant) -> None:
    """Test that correct interface on first try returns immediately."""
    gateway = ConnectMotionGateway(hass)

    with patch(
        "homeassistant.components.motion_blinds.gateway.network.async_get_adapters",
        return_value=MOCK_ADAPTERS_DUAL_NIC,
    ), patch(
        "homeassistant.components.motion_blinds.gateway.AsyncMotionMulticast"
    ) as mock_multicast, patch(
        "homeassistant.components.motion_blinds.gateway.MotionGateway"
    ):
        mock_instance = MagicMock()
        mock_instance.Start_listen = AsyncMock()
        mock_instance.Stop_listen = MagicMock()
        mock_multicast.return_value = mock_instance

        with patch.object(gateway, "check_interface", return_value=True):
            result = await gateway.async_check_interface("192.168.1.1", "testkey")

    assert result == "192.168.1.10"


async def test_check_interface_none_working_falls_back(hass: HomeAssistant) -> None:
    """Test fallback to stored interface when none work."""
    gateway = ConnectMotionGateway(hass, interface="0.0.0.0")

    with patch(
        "homeassistant.components.motion_blinds.gateway.network.async_get_adapters",
        return_value=MOCK_ADAPTERS_DUAL_NIC,
    ), patc
