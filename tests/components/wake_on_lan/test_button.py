"""The tests for the wake on lan button platform."""
import subprocess
from unittest.mock import patch

import pytest

import homeassistant.components.button as button
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def mock_send_magic_packet():
    """Mock magic packet."""
    with patch("wakeonlan.send_magic_packet") as mock_send:
        yield mock_send


async def test_broadcast_config_ip_and_port(hass, mock_send_magic_packet):
    """Test with broadcast address and broadcast port config."""
    mac = "00-01-02-03-04-05"
    broadcast_address = "255.255.255.255"
    port = 999

    assert await async_setup_component(
        hass,
        button.DOMAIN,
        {
            "button": {
                "platform": "wake_on_lan",
                "mac": mac,
                "broadcast_address": broadcast_address,
                "broadcast_port": port,
            }
        },
    )
    await hass.async_block_till_done()

    with patch.object(subprocess, "call", return_value=0):

        await hass.services.async_call(
            button.DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wake_on_lan"},
            blocking=True,
        )

        mock_send_magic_packet.assert_called_with(
            mac, ip_address=broadcast_address, port=port
        )


async def test_broadcast_config_ip(hass, mock_send_magic_packet):
    """Test with only broadcast address."""

    mac = "00-01-02-03-04-05"
    broadcast_address = "255.255.255.255"

    assert await async_setup_component(
        hass,
        button.DOMAIN,
        {
            "button": {
                "platform": "wake_on_lan",
                "mac": mac,
                "broadcast_address": broadcast_address,
            }
        },
    )
    await hass.async_block_till_done()

    with patch.object(subprocess, "call", return_value=0):

        await hass.services.async_call(
            button.DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wake_on_lan"},
            blocking=True,
        )

        mock_send_magic_packet.assert_called_with(mac, ip_address=broadcast_address)


async def test_broadcast_config_port(hass, mock_send_magic_packet):
    """Test with only broadcast port config."""

    mac = "00-01-02-03-04-05"
    port = 999

    assert await async_setup_component(
        hass,
        button.DOMAIN,
        {"button": {"platform": "wake_on_lan", "mac": mac, "broadcast_port": port}},
    )
    await hass.async_block_till_done()

    with patch.object(subprocess, "call", return_value=0):

        await hass.services.async_call(
            button.DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wake_on_lan"},
            blocking=True,
        )

        mock_send_magic_packet.assert_called_with(mac, port=port)
