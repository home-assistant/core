"""Test the Teslemetry media player platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_VOLUME_SET,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import COMMAND_OK, METADATA_NOSCOPE, VEHICLE_DATA_ALT


async def test_media_player(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the media player entities are correct."""

    entry = await setup_platform(hass, [Platform.MEDIA_PLAYER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_media_player_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Tests that the media player entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.MEDIA_PLAYER])
    assert_entities_alt(hass, entry.entry_id, entity_registry, snapshot)


async def test_media_player_offline(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Tests that the media player entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, [Platform.MEDIA_PLAYER])
    state = hass.states.get("media_player.test_media_player")
    assert state.state == MediaPlayerState.OFF


async def test_media_player_noscope(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_metadata: AsyncMock,
) -> None:
    """Tests that the media player entities are correct without required scope."""

    mock_metadata.return_value = METADATA_NOSCOPE
    entry = await setup_platform(hass, [Platform.MEDIA_PLAYER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_media_player_services(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests that the media player services work."""

    await setup_platform(hass, [Platform.MEDIA_PLAYER])

    entity_id = "media_player.test_media_player"

    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.adjust_volume",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5
        call.assert_called_once()

    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.media_toggle_playback",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == MediaPlayerState.PAUSED
        call.assert_called_once()

    # This test will fail without the previous call to pause playback
    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.media_toggle_playback",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PLAY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == MediaPlayerState.PLAYING
        call.assert_called_once()

    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.media_next_track",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        call.assert_called_once()

    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.media_prev_track",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        call.assert_called_once()
