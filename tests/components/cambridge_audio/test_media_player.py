"""Tests for the Cambridge Audio integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.const import (
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import ENTITY_ID

from tests.common import MockConfigEntry

# async def test_entity_attributes(
#     hass: HomeAssistant,
#     mock_stream_magic_client: AsyncMock,
#     mock_config_entry: MockConfigEntry,
#     monkeypatch: pytest.MonkeyPatch,
#     device_registry: dr.DeviceRegistry,
# ) -> None:
#     """Test entity attributes."""
#     entry = await setup_integration(hass, mock_config_entry)
#     await mock_stream_magic_client.mock_state_update()
#     await hass.async_block_till_done()
#
#     # Attributes when device is on
#     state = hass.states.get(ENTITY_ID)
#     attrs = state.attributes
#     assert state.state == STATE_PLAYING
#     assert attrs[ATTR_DEVICE_CLASS] == MediaPlayerDeviceClass.RECEIVER
#     await mock_stream_magic_client.mock_state_update()
#     await hass.async_block_till_done()
#     await mock_stream_magic_client.mock_state_update()
#     await hass.async_block_till_done()
#
#     await mock_stream_magic_client.mock_state_update()
#     await hass.async_block_till_done()
#
#     assert False
#     # assert attrs[ATTR_MEDIA_VOLUME_MUTED] is False
#     # assert attrs[ATTR_MEDIA_VOLUME_LEVEL] == 0.37
#     # assert attrs[ATTR_INPUT_SOURCE] == "Live TV"
#     # assert attrs[ATTR_INPUT_SOURCE_LIST] == ["Input01", "Input02", "Live TV"]
#     # assert attrs[ATTR_MEDIA_CONTENT_TYPE] == MediaType.CHANNEL
#     # assert attrs[ATTR_MEDIA_TITLE] == "Channel 1"
#     # assert attrs[ATTR_SOUND_OUTPUT] == "speaker"
#
#     # mock_stream_magic_client.state = State.from_json(
#     #     load_fixture("airplay_get_state.json", DOMAIN)
#     # )
#     # mock_stream_magic_client.play_state = PlayState.from_json(
#     #     load_fixture("airplay_get_play_state.json", DOMAIN)
#     # )
#     # mock_stream_magic_client.now_playing = NowPlaying.from_json(
#     #     load_fixture("airplay_get_now_playing.json", DOMAIN)
#     # )
#
#     # assert [
#     #     MediaPlayerEntityFeature.VOLUME_MUTE,
#     #     MediaPlayerEntityFeature.VOLUME_SET,
#     #     MediaPlayerEntityFeature.VOLUME_STEP,
#     # ] in attrs[ATTR_SUPPORTED_FEATURES]
#
#     # # Volume level not available
#     # monkeypatch.setattr(client, "volume", None)
#     # await client.mock_state_update()
#     # attrs = hass.states.get(ENTITY_ID).attributes
#     #
#     # assert attrs.get(ATTR_MEDIA_VOLUME_LEVEL) is None
#     #
#     # # Channel change
#     # monkeypatch.setattr(client, "current_channel", CHANNEL_2)
#     # await client.mock_state_update()
#     # attrs = hass.states.get(ENTITY_ID).attributes
#     #
#     # assert attrs[ATTR_MEDIA_TITLE] == "Channel Name 2"
#     #
#     # # Device Info
#     # device = device_registry.async_get_device(identifiers={(DOMAIN, entry.unique_id)})
#     #
#     # assert device
#     # assert device.identifiers == {(DOMAIN, entry.unique_id)}
#     # assert device.manufacturer == "LG"
#     # assert device.name == TV_NAME
#     # assert device.sw_version == "major.minor"
#     # assert device.model == "TVFAKE"
#     #
#     # # Sound output when off
#     # monkeypatch.setattr(client, "sound_output", None)
#     # monkeypatch.setattr(client, "is_on", False)
#     # await client.mock_state_update()
#     # state = hass.states.get(ENTITY_ID)
#     #
#     # assert state.state == STATE_OFF
#     # assert state.attributes.get(ATTR_SOUND_OUTPUT) is None


@pytest.mark.parametrize(
    ("power_state", "play_state", "media_player_state"),
    [
        (True, "NETWORK", STATE_STANDBY),
        (False, "NETWORK", STATE_STANDBY),
        (False, "play", STATE_OFF),
        (True, "play", STATE_PLAYING),
        (True, "pause", STATE_PAUSED),
        (True, "connecting", STATE_BUFFERING),
        (True, "stop", STATE_IDLE),
        (True, "ready", STATE_IDLE),
    ],
)
async def test_entity_state(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    device_registry: dr.DeviceRegistry,
    power_state: bool,
    play_state: str,
    media_player_state: str,
) -> None:
    """Test media player state."""
    await setup_integration(hass, mock_config_entry)
    mock_stream_magic_client.state.power = power_state
    mock_stream_magic_client.play_state.state = play_state
    await mock_stream_magic_client.mock_state_update()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == media_player_state
