"""The tests for Media Player device actions."""
from components.media_player import (
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.media_player import DOMAIN
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)

EXPECTED_ACTION_TYPES = [
    "turn_on",
    "turn_off",
    "toggle",
    "volume_up",
    "volume_down",
    "media_play",
    "media_pause",
    "media_play_pause",
    "media_stop",
    "media_next_track",
    "media_previous_track",
    "clear_playlist",
]


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_get_actions(hass, device_reg, entity_reg):
    """Test we get the expected actions from a media_player."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        supported_features=SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        | SUPPORT_VOLUME_SET
        | SUPPORT_VOLUME_STEP
        | SUPPORT_PLAY
        | SUPPORT_PAUSE
        | SUPPORT_STOP
        | SUPPORT_NEXT_TRACK
        | SUPPORT_PREVIOUS_TRACK
        | SUPPORT_CLEAR_PLAYLIST,
    )

    expected_actions = [
        {
            "domain": DOMAIN,
            "type": action_type,
            "device_id": device_entry.id,
            "entity_id": "media_player.test_5678",
        }
        for action_type in EXPECTED_ACTION_TYPES
    ]

    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_action(hass):
    """Test for turn_on and turn_off actions."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": f"test_event_{action_type}",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "media_player.entity",
                        "type": action_type,
                    },
                }
                for action_type in EXPECTED_ACTION_TYPES
            ]
        },
    )

    turn_off_calls = async_mock_service(hass, DOMAIN, "turn_off")
    turn_on_calls = async_mock_service(hass, DOMAIN, "turn_on")
    toggle_calls = async_mock_service(hass, DOMAIN, "toggle")

    volume_up_calls = async_mock_service(hass, DOMAIN, "volume_up")
    volume_down_calls = async_mock_service(hass, DOMAIN, "volume_down")

    clear_playlist_calls = async_mock_service(hass, DOMAIN, "clear_playlist")

    next_track_calls = async_mock_service(hass, DOMAIN, "media_next_track")
    previous_track_calls = async_mock_service(hass, DOMAIN, "media_previous_track")

    media_play_calls = async_mock_service(hass, DOMAIN, "media_play")
    media_pause_calls = async_mock_service(hass, DOMAIN, "media_pause")
    media_play_pause_calls = async_mock_service(hass, DOMAIN, "media_play_pause")
    media_stop_calls = async_mock_service(hass, DOMAIN, "media_stop")

    hass.bus.async_fire("test_event_turn_off")
    await hass.async_block_till_done()
    assert len(turn_off_calls) == 1
    assert len(turn_on_calls) == 0

    hass.bus.async_fire("test_event_turn_on")
    await hass.async_block_till_done()
    assert len(turn_off_calls) == 1
    assert len(turn_on_calls) == 1

    hass.bus.async_fire("test_event_toggle")
    await hass.async_block_till_done()
    assert len(turn_off_calls) == 1
    assert len(turn_on_calls) == 1
    assert len(toggle_calls) == 1

    hass.bus.async_fire("test_event_toggle")
    await hass.async_block_till_done()
    assert len(turn_off_calls) == 1
    assert len(turn_on_calls) == 1
    assert len(toggle_calls) == 2

    hass.bus.async_fire("test_event_volume_up")
    await hass.async_block_till_done()
    assert len(volume_up_calls) == 1
    assert len(volume_down_calls) == 0

    hass.bus.async_fire("test_event_volume_down")
    await hass.async_block_till_done()
    assert len(volume_up_calls) == 1
    assert len(volume_down_calls) == 1

    hass.bus.async_fire("test_event_clear_playlist")
    await hass.async_block_till_done()
    assert len(clear_playlist_calls) == 1

    hass.bus.async_fire("test_event_media_next_track")
    await hass.async_block_till_done()
    assert len(next_track_calls) == 1
    assert len(previous_track_calls) == 0

    hass.bus.async_fire("test_event_media_previous_track")
    await hass.async_block_till_done()
    assert len(next_track_calls) == 1
    assert len(previous_track_calls) == 1

    hass.bus.async_fire("test_event_media_play")
    await hass.async_block_till_done()
    assert len(media_play_calls) == 1
    assert len(media_pause_calls) == 0
    assert len(media_play_pause_calls) == 0
    assert len(media_stop_calls) == 0

    hass.bus.async_fire("test_event_media_pause")
    await hass.async_block_till_done()
    assert len(media_play_calls) == 1
    assert len(media_pause_calls) == 1
    assert len(media_play_pause_calls) == 0
    assert len(media_stop_calls) == 0

    hass.bus.async_fire("test_event_media_play_pause")
    await hass.async_block_till_done()
    assert len(media_play_calls) == 1
    assert len(media_pause_calls) == 1
    assert len(media_play_pause_calls) == 1
    assert len(media_stop_calls) == 0

    hass.bus.async_fire("test_event_media_stop")
    await hass.async_block_till_done()
    assert len(media_play_calls) == 1
    assert len(media_pause_calls) == 1
    assert len(media_play_pause_calls) == 1
    assert len(media_stop_calls) == 1

    assert len(turn_off_calls) == 1
    assert len(turn_on_calls) == 1
    assert len(toggle_calls) == 2
    assert len(volume_up_calls) == 1
    assert len(volume_down_calls) == 1
    assert len(clear_playlist_calls) == 1
    assert len(next_track_calls) == 1
    assert len(previous_track_calls) == 1
