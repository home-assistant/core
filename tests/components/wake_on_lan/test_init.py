"""Tests for Wake On LAN component."""
from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wake_on_lan import DOMAIN, SERVICE_SEND_MAGIC_PACKET
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_send_magic_packet(hass: HomeAssistant) -> None:
    """Test of send magic packet service call."""
    with patch("homeassistant.components.wake_on_lan.wakeonlan") as mocked_wakeonlan:
        mac = "aa:bb:cc:dd:ee:ff"
        bc_ip = "192.168.255.255"
        bc_port = 999

        await async_setup_component(hass, DOMAIN, {})

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MAGIC_PACKET,
            {"mac": mac, "broadcast_address": bc_ip, "broadcast_port": bc_port},
            blocking=True,
        )
        assert len(mocked_wakeonlan.mock_calls) == 1
        assert mocked_wakeonlan.mock_calls[-1][1][0] == mac
        assert mocked_wakeonlan.mock_calls[-1][2]["ip_address"] == bc_ip
        assert mocked_wakeonlan.mock_calls[-1][2]["port"] == bc_port

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MAGIC_PACKET,
            {"mac": mac, "broadcast_address": bc_ip},
            blocking=True,
        )
        assert len(mocked_wakeonlan.mock_calls) == 2
        assert mocked_wakeonlan.mock_calls[-1][1][0] == mac
        assert mocked_wakeonlan.mock_calls[-1][2]["ip_address"] == bc_ip
        assert "port" not in mocked_wakeonlan.mock_calls[-1][2]

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_MAGIC_PACKET,
            {"mac": mac, "broadcast_port": bc_port},
            blocking=True,
        )
        assert len(mocked_wakeonlan.mock_calls) == 3
        assert mocked_wakeonlan.mock_calls[-1][1][0] == mac
        assert mocked_wakeonlan.mock_calls[-1][2]["port"] == bc_port
        assert "ip_address" not in mocked_wakeonlan.mock_calls[-1][2]

        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEND_MAGIC_PACKET,
                {"broadcast_address": bc_ip},
                blocking=True,
            )
        assert len(mocked_wakeonlan.mock_calls) == 3

        await hass.services.async_call(
            DOMAIN, SERVICE_SEND_MAGIC_PACKET, {"mac": mac}, blocking=True
        )
        assert len(mocked_wakeonlan.mock_calls) == 4
        assert mocked_wakeonlan.mock_calls[-1][1][0] == mac
        assert not mocked_wakeonlan.mock_calls[-1][2]


async def test_setup_from_integration_yaml(hass: HomeAssistant) -> None:
    """Test setup from integration yaml."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "mac": "00-01-02-03-04-05",
                    "host": "validhostname",
                },
                {
                    "mac": "06-07-08-09-0A-0B",
                    "host": "validhostname2",
                    "name": "Friendly Name",
                },
            ],
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wake_on_lan")
    state2 = hass.states.get("switch.friendly_name")

    assert state.state == STATE_OFF
    assert state2.state == STATE_OFF

    with patch.object(subprocess, "call", return_value=0):

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert state.state == STATE_ON

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.wake_on_lan"},
            blocking=True,
        )

        state = hass.states.get("switch.wake_on_lan")
        assert state.state == STATE_ON
