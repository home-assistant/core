"""Transmission service platform tests."""
from unittest.mock import patch

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN


async def test_switches(hass, torrent_info):
    """Test the Transmission switch platforms."""
    transmission_switch = hass.states.get("switch.transmission_switch")
    assert transmission_switch is not None
    assert transmission_switch.state == "on"

    with patch("transmissionrpc.Client.stop_torrent") as func:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_off",
            {"entity_id": "switch.transmission_switch"},
            blocking=True,
        )
        func.assert_called_with([1, 2, 3, 4, 5])

    with patch("transmissionrpc.Client.start_all") as func:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {"entity_id": "switch.transmission_switch"},
            blocking=True,
        )
        func.assert_called()

    transmission_turtle_mode = hass.states.get("switch.transmission_turtle_mode")
    assert transmission_turtle_mode is not None
    assert transmission_turtle_mode.state == "on"

    with patch("transmissionrpc.Client.set_session") as func:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_off",
            {"entity_id": "switch.transmission_turtle_mode"},
            blocking=True,
        )
        func.assert_called_with(alt_speed_enabled=False)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {"entity_id": "switch.transmission_turtle_mode"},
            blocking=True,
        )
        func.assert_called_with(alt_speed_enabled=True)
