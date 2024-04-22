"""The tests for the Ring binary sensor platform."""

from time import time
from unittest.mock import patch

import requests_mock

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

    front_ding_state = hass.states.get("binary_sensor.front_door_ding")
    assert front_ding_state is not None
    assert front_ding_state.state == "off"

    ingress_ding_state = hass.states.get("binary_sensor.ingress_ding")
    assert ingress_ding_state is not None
    assert ingress_ding_state.state == "off"
