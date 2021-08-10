"""Test Alexa entity representation."""
from unittest.mock import patch

from homeassistant.components.alexa import smart_home
from homeassistant.const import __version__

from . import DEFAULT_CONFIG, get_new_request


async def test_unsupported_domain(hass):
    """Discovery ignores entities of unknown domains."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("woz.boop", "on", {"friendly_name": "Boop Woz"})

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)

    assert "event" in msg
    msg = msg["event"]

    assert not msg["payload"]["endpoints"]


async def test_serialize_discovery(hass):
    """Test we handle an interface raising unexpectedly during serialize discovery."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("switch.bla", "on", {"friendly_name": "Boop Woz"})

    msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)

    assert "event" in msg
    msg = msg["event"]
    endpoint = msg["payload"]["endpoints"][0]

    assert endpoint["additionalAttributes"] == {
        "manufacturer": "Home Assistant",
        "model": "switch",
        "softwareVersion": __version__,
        "customIdentifier": "mock-user-id-switch.bla",
    }


async def test_serialize_discovery_recovers(hass, caplog):
    """Test we handle an interface raising unexpectedly during serialize discovery."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("switch.bla", "on", {"friendly_name": "Boop Woz"})

    with patch(
        "homeassistant.components.alexa.capabilities.AlexaPowerController.serialize_discovery",
        side_effect=TypeError,
    ):
        msg = await smart_home.async_handle_message(hass, DEFAULT_CONFIG, request)

    assert "event" in msg
    msg = msg["event"]

    interfaces = {
        ifc["interface"] for ifc in msg["payload"]["endpoints"][0]["capabilities"]
    }

    assert "Alexa.PowerController" not in interfaces
    assert (
        f"Error serializing Alexa.PowerController discovery for {hass.states.get('switch.bla')}"
        in caplog.text
    )
