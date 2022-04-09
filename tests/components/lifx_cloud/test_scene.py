"""Tests for lifx_cloud scenes."""
from homeassistant.components.lifx_cloud.scene import map_to_lifx_request


def test_do_not_send_duration_when_transition_is_absent():
    """Hass shouldn't send duration if the user didn't specify it."""
    service_args = {}
    body = map_to_lifx_request(service_args)
    assert "duration" not in body


def test_send_transition_as_duration():
    """When a 'transition' is passed to scene.turn_on, we should give it to LIFX as 'duration'."""
    service_args = {"transition": 3.0}
    body = map_to_lifx_request(service_args)
    assert body.get("duration") == 3.0
