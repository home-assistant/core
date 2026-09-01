"""Test the Frontier Silicon media player entity."""

from datetime import timedelta
from unittest.mock import AsyncMock

from afsapi import FSConnectionError, FSNotImplementedError, PlayCaps
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.frontier_silicon.media_player import AFSAPIMediaPlayer
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    STATE_IDLE,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

MEDIA_PLAYER_ENTITY_ID = "media_player.name_of_the_device"
DST_SWITCH_ENTITY_ID = "switch.name_of_the_device_daylight_saving_time"

_FULL_PLAY_CAPS = (
    PlayCaps.PAUSE
    | PlayCaps.STOP
    | PlayCaps.SKIP_NEXT
    | PlayCaps.SKIP_PREVIOUS
    | PlayCaps.FAST_FORWARD
    | PlayCaps.REWIND
    | PlayCaps.SHUFFLE
    | PlayCaps.REPEAT
    | PlayCaps.SEEK
    | PlayCaps.APPLY_FEEDBACK
    | PlayCaps.SCROBBLING
    | PlayCaps.ADD_PRESET
    | PlayCaps.THUMBS_UP
    | PlayCaps.THUMBS_DOWN
    | PlayCaps.SKIP_FORWARD
    | PlayCaps.SKIP_BACKWARD
    | PlayCaps.REPEAT_ONE
)


@pytest.mark.parametrize(
    ("error", "translation_key", "message"),
    [
        (FSConnectionError("Connection failed"), "connection_error", None),
        (
            FSNotImplementedError("Command is not implemented"),
            "api_error",
            "Command is not implemented",
        ),
    ],
)
async def test_async_media_previous_track_maps_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    error: Exception,
    translation_key: str,
    message: str | None,
) -> None:
    """Test previous track maps API failures to Home Assistant errors."""
    mock_afsapi.get_power.return_value = True
    mock_afsapi.get_play_caps.return_value = _FULL_PLAY_CAPS
    mock_afsapi.rewind.side_effect = error

    await setup_integration(hass, config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders["command"] == "media_previous_track"

    assert (
        message is None or message in exc_info.value.translation_placeholders["message"]
    )


async def test_async_media_caps(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
) -> None:
    """Test AFSAPI play caps translation to MediaPlayerEntityFeatures."""
    mock_afsapi.get_play_caps.return_value = _FULL_PLAY_CAPS

    await setup_integration(hass, config_entry)

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        AFSAPIMediaPlayer._BASE_SUPPORTED_FEATURES
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.REPEAT_SET
        | MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )


async def test_media_player_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_afsapi: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update of a device which is powered on."""
    await setup_integration(hass, config_entry)

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device_entry = devices[0]

    entities = er.async_entries_for_device(entity_registry, device_entry.id)
    assert len(entities) == 2

    # Power on the device and advance time to trigger a poll
    mock_afsapi.get_power.return_value = True
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).state == STATE_IDLE


async def test_async_update_disconnect(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_afsapi: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an update with a disconnect can change device availability."""
    await setup_integration(hass, config_entry)

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device_entry = devices[0]

    entities = er.async_entries_for_device(entity_registry, device_entry.id)
    assert len(entities) == 2

    # Device starts in off state
    assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).state == STATE_OFF

    # Make the device raise a connection error on the next poll
    mock_afsapi.get_power.side_effect = FSConnectionError
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).state == STATE_UNAVAILABLE

    # Reset device error state
    mock_afsapi.get_power.side_effect = None
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(MEDIA_PLAYER_ENTITY_ID).state == STATE_OFF
