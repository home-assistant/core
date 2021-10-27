"""The tests for the Ring binary sensor platform."""
from time import time
from unittest.mock import patch

from .common import setup_platform


async def test_binary_sensor(hass, requests_mock):
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
