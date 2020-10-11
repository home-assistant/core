"""The tests for the KMtronic switch platform."""
from homeassistant.components.kmtronic.const import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_relay_on_off(hass, aioclient_mock):
    """Tests the relay turns on correctly."""

    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        text="<response><relay0>0</relay0><relay1>0</relay1></response>",
    )

    MockConfigEntry(
        domain=DOMAIN, data={"host": "1.1.1.1", "username": "foo", "password": "bar"}
    ).add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Mocks the response for turning a relay1 on
    aioclient_mock.get(
        "http://1.1.1.1/FF0101",
        text="",
    )

    state = hass.states.get("switch.relay1")
    assert state.state == "off"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.relay1"}, blocking=True
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "on"

    # Mocks the response for turning a relay1 off
    aioclient_mock.get(
        "http://1.1.1.1/FF0100",
        text="",
    )

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.relay1"}, blocking=True
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "off"
