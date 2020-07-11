"""Test Alexa entity representation."""
from homeassistant.components.alexa import smart_home

from . import DEFAULT_CONFIG, get_new_request


async def test_unsupported_domain(hass):
    """Discovery ignores entities of unknown domains."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("woz.boop", "on", {"friendly_name": "Boop Woz"})

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)

    assert "event" in msg
    msg = msg["event"]

    assert not msg["payload"]["endpoints"]
