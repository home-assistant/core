"""Test the Frontier Silicon media player entity."""

import logging
from unittest.mock import AsyncMock, patch

from afsapi import FSConnectionError, FSNotImplementedError, PlayCaps
import pytest

from homeassistant.components.frontier_silicon.media_player import AFSAPIMediaPlayer
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import FakeAFSAPIDevice

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


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
    error: Exception, translation_key: str, message: str | None
) -> None:
    """Test previous track maps API failures to Home Assistant errors."""
    fs_device = AsyncMock()
    fs_device.rewind.side_effect = error
    mock_config_entry = MockConfigEntry()
    entity = AFSAPIMediaPlayer(mock_config_entry, fs_device)

    with pytest.raises(HomeAssistantError) as exc_info:
        await entity.async_media_previous_track()

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders["command"] == "media_previous_track"

    assert (
        message is None or message in exc_info.value.translation_placeholders["message"]
    )


async def test_async_media_caps() -> None:
    """Test AFSAPI play caps translation to MediaPlayerEntityFeatures."""
    fs_device = AsyncMock()
    fs_device.get_power.return_value = False
    fs_device.get_play_caps.return_value = (
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
    mock_config_entry = MockConfigEntry()
    entity = AFSAPIMediaPlayer(mock_config_entry, fs_device)
    await entity.async_update()
    assert entity.supported_features == (
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
    fake_afsapi_dev: FakeAFSAPIDevice,
) -> None:
    """Test update of a device which is powered on."""
    # Connect device
    with patch(
        "homeassistant.components.frontier_silicon.AFSAPI",
        FakeAFSAPIDevice,
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify device exists
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device_entry = devices[0]

    # Verify device has the expected number of entities
    expected_num_entities = 1
    entities = er.async_entries_for_device(entity_registry, device_entry.id)
    assert len(entities) == expected_num_entities

    # Power on the fake device
    fake_afsapi_dev.has_power = True
    # get hass to do an update
    await async_update_entity(hass, entities[0].entity_id)
    assert hass.states.get(entities[0].entity_id).state == STATE_IDLE


async def test_async_update_disconnect(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_afsapi_dev: FakeAFSAPIDevice,
) -> None:
    """Test that an update with a disconnect can change device availability."""

    # Connect device
    with patch(
        "homeassistant.components.frontier_silicon.AFSAPI",
        FakeAFSAPIDevice,
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify device exists
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device_entry = devices[0]

    # Verify device has the expected number of entities
    expected_num_entities = 1
    entities = er.async_entries_for_device(entity_registry, device_entry.id)
    assert len(entities) == expected_num_entities

    # Get hass to do an update
    await async_update_entity(hass, entities[0].entity_id)
    # Fake device starts in off state
    assert hass.states.get(entities[0].entity_id).state == STATE_OFF

    # Make the fake device raise a connection error next time get_power is called
    fake_afsapi_dev.fail_get_power = True
    # get hass to do an update
    await async_update_entity(hass, entities[0].entity_id)
    # Check device availability, should now be offline
    assert hass.states.get(entities[0].entity_id).state == STATE_UNAVAILABLE

    # Reset device error state
    fake_afsapi_dev.fail_get_power = False
    await async_update_entity(hass, entities[0].entity_id)
    # Fake device should be back in off state
    assert hass.states.get(entities[0].entity_id).state == STATE_OFF
