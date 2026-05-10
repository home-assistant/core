"""Tests for the Yoto media player platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_VOLUME_SET,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "media_player.nursery_yoto"


async def test_media_player_state(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_token_hex: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Snapshot the media player entity state."""
    freezer.move_to("2026-05-08T12:00:00+00:00")
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "method", "args"),
    [
        (SERVICE_MEDIA_PLAY, "resume_player", ("player-test",)),
        (SERVICE_MEDIA_PAUSE, "pause_player", ("player-test",)),
        (SERVICE_MEDIA_STOP, "stop_player", ("player-test",)),
        (SERVICE_MEDIA_NEXT_TRACK, "next_track", ("player-test",)),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "previous_track", ("player-test",)),
    ],
)
async def test_playback_commands(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
    service: str,
    method: str,
    args: tuple[str, ...],
) -> None:
    """Playback service calls reach the manager."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    getattr(mock_yoto_manager, method).assert_called_once_with(*args)


async def test_set_volume(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Volume is forwarded as an integer 0-100."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )

    mock_yoto_manager.set_volume.assert_called_once_with("player-test", 50)


async def test_play_media_with_full_id(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """play_media parses the structured media id."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": "card-test+02+02-INT+30",
        },
        blocking=True,
    )

    mock_yoto_manager.play_card.assert_called_once_with(
        "player-test", "card-test", 30, None, "02", "02-INT"
    )


async def test_seek(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Seek delegates to the manager with the integer position."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_SEEK_POSITION: 30},
        blocking=True,
    )

    mock_yoto_manager.seek.assert_called_once_with("player-test", 30)


async def test_play_media_invalid_seconds(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """A malformed seconds segment raises ServiceValidationError."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "media_content_type": "music",
                "media_content_id": "card-test+02+02-INT+abc",
            },
            blocking=True,
        )


async def test_play_media_card_only(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """play_media defaults missing fields to None."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": "card-test",
        },
        blocking=True,
    )

    mock_yoto_manager.play_card.assert_called_once_with(
        "player-test", "card-test", None, None, None, None
    )
