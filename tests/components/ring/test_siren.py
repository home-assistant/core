"""The tests for the Ring button platform."""

from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.SIREN)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("siren.downstairs_siren")
    assert entry.unique_id == "123456-siren"


async def test_sirens_report_correctly(hass, requests_mock):
    """Tests that the initial state of a device that should be on is correct."""
    await setup_platform(hass, Platform.SIREN)

    state = hass.states.get("siren.downstairs_siren")
    assert state.attributes.get("friendly_name") == "Downstairs Siren"
    assert state.state == "unknown"


async def test_default_ding_chime_can_be_played(hass, requests_mock):
    """Tests the play chime request is sent correctly."""
    await setup_platform(hass, Platform.SIREN)

    # Mocks the response for playing a test sound
    requests_mock.post(
        "https://api.ring.com/clients_api/chimes/123456/play_sound",
        text="SUCCESS",
    )
    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": "siren.downstairs_siren"},
        blocking=True,
    )

    await hass.async_block_till_done()

    assert requests_mock.request_history[-1].url.startswith(
        "https://api.ring.com/clients_api/chimes/123456/play_sound?"
    )
    assert "kind=ding" in requests_mock.request_history[-1].url

    state = hass.states.get("siren.downstairs_siren")
    assert state.state == "unknown"


async def test_toggle_plays_default_chime(hass, requests_mock):
    """Tests the play chime request is sent correctly when toggled."""
    await setup_platform(hass, Platform.SIREN)

    # Mocks the response for playing a test sound
    requests_mock.post(
        "https://api.ring.com/clients_api/chimes/123456/play_sound",
        text="SUCCESS",
    )
    await hass.services.async_call(
        "siren",
        "toggle",
        {"entity_id": "siren.downstairs_siren"},
        blocking=True,
    )

    await hass.async_block_till_done()

    assert requests_mock.request_history[-1].url.startswith(
        "https://api.ring.com/clients_api/chimes/123456/play_sound?"
    )
    assert "kind=ding" in requests_mock.request_history[-1].url

    state = hass.states.get("siren.downstairs_siren")
    assert state.state == "unknown"


async def test_explicit_ding_chime_can_be_played(hass, requests_mock):
    """Tests the play chime request is sent correctly."""
    await setup_platform(hass, Platform.SIREN)

    # Mocks the response for playing a test sound
    requests_mock.post(
        "https://api.ring.com/clients_api/chimes/123456/play_sound",
        text="SUCCESS",
    )
    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": "siren.downstairs_siren", "tone": "ding"},
        blocking=True,
    )

    await hass.async_block_till_done()

    assert requests_mock.request_history[-1].url.startswith(
        "https://api.ring.com/clients_api/chimes/123456/play_sound?"
    )
    assert "kind=ding" in requests_mock.request_history[-1].url

    state = hass.states.get("siren.downstairs_siren")
    assert state.state == "unknown"


async def test_motion_chime_can_be_played(hass, requests_mock):
    """Tests the play chime request is sent correctly."""
    await setup_platform(hass, Platform.SIREN)

    # Mocks the response for playing a test sound
    requests_mock.post(
        "https://api.ring.com/clients_api/chimes/123456/play_sound",
        text="SUCCESS",
    )
    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": "siren.downstairs_siren", "tone": "motion"},
        blocking=True,
    )

    await hass.async_block_till_done()

    assert requests_mock.request_history[-1].url.startswith(
        "https://api.ring.com/clients_api/chimes/123456/play_sound?"
    )
    assert "kind=motion" in requests_mock.request_history[-1].url

    state = hass.states.get("siren.downstairs_siren")
    assert state.state == "unknown"
