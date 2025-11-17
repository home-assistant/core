"""Tests for Apple TV media-player power and listener-driven regressions."""

from pyatv.const import DeviceState, FeatureName, FeatureState
import pytest

from homeassistant.components import media_player
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.asyncio


async def _one_media_player(hass: HomeAssistant) -> str:
    """Return the single Apple TV media player entity id."""
    entities = hass.states.async_entity_ids(media_player.DOMAIN)
    assert entities, "Media player entity was not created"
    return entities[0]


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_power_state_from_remote(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Test power on/off updates media_player state changing via remote. (e.g. by the Apple TV itself)."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    # Turn off
    await atv.power.turn_off()
    await hass.async_block_till_done()
    state_off = hass.states.get(entity_id).state

    powerstate_supported = atv.features.in_state(
        FeatureState.Available, FeatureName.PowerState
    )
    if powerstate_supported:
        assert state_off == media_player.MediaPlayerState.OFF
    else:
        assert state_off == "unknown"

    # Turn on
    await atv.power.turn_on()
    await hass.async_block_till_done()
    state_on = hass.states.get(entity_id).state

    if powerstate_supported:
        assert state_on == media_player.MediaPlayerState.ON
    else:
        # Without powerstate feature we cannot know real power its only updated when playing
        assert state_on == "unknown"


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_power_state_using_services(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Test power on/off using media_player services."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)
    powerstate_supported = atv.features.in_state(
        FeatureState.Available, FeatureName.PowerState
    )
    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.PLAYING

    await hass.services.async_call(
        "media_player",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id).state
    if powerstate_supported:
        assert state == media_player.MediaPlayerState.OFF
    else:  # Without powerstate feature player remains PLAYING
        assert state == media_player.MediaPlayerState.PLAYING

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id).state
    if powerstate_supported:
        assert state == media_player.MediaPlayerState.PLAYING
    else:  # Without powerstate feature player remains PLAYING
        assert state == media_player.MediaPlayerState.PLAYING


@pytest.mark.parametrize("setup_runtime_integration", [True, False], indirect=True)
async def test_listener_playing_state_update(
    hass: HomeAssistant, setup_runtime_integration
) -> None:
    """Test that playing state updates via listener work."""
    _, atv = setup_runtime_integration
    entity_id = await _one_media_player(hass)

    await atv.push_updater.trigger_playing(DeviceState.Idle)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.IDLE

    await atv.push_updater.trigger_playing(DeviceState.Playing)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.PLAYING

    await atv.push_updater.trigger_playing(DeviceState.Paused)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == media_player.MediaPlayerState.PAUSED
