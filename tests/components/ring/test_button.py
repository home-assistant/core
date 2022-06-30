"""The tests for the Ring button platform."""

from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.BUTTON)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("button.downstairs_play_chime_ding")
    assert entry.unique_id == "123456-play-chime-ding"

    entry = entity_registry.async_get("button.downstairs_play_chime_motion")
    assert entry.unique_id == "123456-play-chime-motion"


async def test_play_chime_buttons_report_correctly(hass, requests_mock):
    """Tests that the initial state of a device that should be on is correct."""
    await setup_platform(hass, Platform.BUTTON)

    state = hass.states.get("button.downstairs_play_chime_ding")
    assert state.attributes.get("friendly_name") == "Downstairs Play chime: ding"
    assert state.attributes.get("icon") == "mdi:bell-ring"

    state = hass.states.get("button.downstairs_play_chime_motion")
    assert state.attributes.get("friendly_name") == "Downstairs Play chime: motion"
    assert state.attributes.get("icon") == "mdi:bell-ring"


async def test_chime_can_be_played(hass, requests_mock):
    """Tests the play chime request is sent correctly."""
    await setup_platform(hass, Platform.BUTTON)

    # Mocks the response for playing a test sound
    requests_mock.post(
        "https://api.ring.com/clients_api/chimes/123456/play_sound",
        text="SUCCESS",
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.downstairs_play_chime_ding"},
        blocking=True,
    )

    await hass.async_block_till_done()

    assert requests_mock.request_history[-1].url.startswith(
        "https://api.ring.com/clients_api/chimes/123456/play_sound?"
    )
    assert "kind=ding" in requests_mock.request_history[-1].url
