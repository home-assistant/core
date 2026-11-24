"""Test the Motionblinds config flow."""

import logging
from unittest.mock import Mock, patch

from motionblinds import DEVICE_TYPES_WIFI, BlindType
import pytest

from homeassistant.components.motion_blinds.gateway import (
    ConnectMotionGateway,
    device_name,
)
from homeassistant.core import HomeAssistant

TEST_BLIND_MAC = "abcdefghujkl0001"
TEST_HOST = "1.2.3.4"
TEST_API_KEY = "12ab345c-d67e-8f"


async def test_device_name(hass: HomeAssistant) -> None:
    """test_device_name."""
    blind = Mock()
    blind.blind_type = BlindType.RollerBlind.name
    blind.mac = TEST_BLIND_MAC
    assert device_name(blind) == "RollerBlind 0001"

    blind.device_type = DEVICE_TYPES_WIFI[0]
    assert device_name(blind) == "RollerBlind"


async def test_connect_gateway_timeout_no_error_spam(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed connect attempt cleans up and does not log an error.

    Regression test for https://github.com/home-assistant/core/issues/188448 .
    Retried setup attempts must not spam ERROR logs, and a previous multicast
    callback for the host must be unregistered before a new gateway registers.
    """
    multicast = Mock()
    connect = ConnectMotionGateway(hass, multicast=multicast)

    gateway = Mock()
    gateway.GetDeviceList.side_effect = TimeoutError

    with (
        patch(
            "homeassistant.components.motion_blinds.gateway.MotionGateway",
            return_value=gateway,
        ),
        caplog.at_level(logging.DEBUG),
    ):
        assert await connect.async_connect_gateway(TEST_HOST, TEST_API_KEY) is False

    multicast.Unregister_motion_gateway.assert_called_once_with(TEST_HOST)
    assert "Timeout trying to connect" in caplog.text
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
