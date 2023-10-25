"""The tests for the Ring binary sensor platform."""
import asyncio
from time import time
from unittest.mock import patch

import requests_mock

from homeassistant.components.ring import DOMAIN, RingEvent
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_binary_sensor(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test the Ring binary sensors."""
    with patch(
        "ring_doorbell.Ring.active_alerts",
        return_value=[
            {
                "kind": "motion",
                "doorbot_id": 987654,
                "state": "ringing",
                "now": time(),
                "expires_in": 180,
            }
        ],
    ):
        await setup_platform(hass, "binary_sensor")

    motion_state = hass.states.get("binary_sensor.front_door_motion")
    assert motion_state is not None
    assert motion_state.state == "on"
    assert motion_state.attributes["device_class"] == "motion"

    ding_state = hass.states.get("binary_sensor.front_door_ding")
    assert ding_state is not None
    assert ding_state.state == "off"


async def test_dings(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test the Ring binary sensors."""

    mock_entry = await setup_platform(hass, "binary_sensor")

    motion_state = hass.states.get("binary_sensor.front_door_motion")
    assert motion_state is not None
    assert motion_state.state == "off"
    assert motion_state.attributes["device_class"] == "motion"

    dings_data = hass.data[DOMAIN][mock_entry.entry_id]["dings_data"]
    expires_in = 0
    re = RingEvent(12, 987654, "Foo", "doorbot", time(), expires_in, "motion", "human")
    with patch(
        "ring_doorbell.Ring.active_alerts",
        return_value=[re],
    ):
        dings_data.on_event(re)

        motion_state = hass.states.get("binary_sensor.front_door_motion")
        assert motion_state is not None
        assert motion_state.state == "on"
        assert motion_state.attributes["device_class"] == "motion"
        ding_state = hass.states.get("binary_sensor.front_door_ding")
        assert ding_state is not None
        assert ding_state.state == "off"

    await hass.async_block_till_done()
    await asyncio.sleep(expires_in)
    motion_state = hass.states.get("binary_sensor.front_door_motion")
    assert motion_state is not None
    assert motion_state.state == "off"
    assert motion_state.attributes["device_class"] == "motion"
