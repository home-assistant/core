"""Tests for the Yoto media player platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from yoto_api import YotoError

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
    SERVICE_VOLUME_SET,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "media_player.nursery_yoto"

pytestmark = pytest.mark.usefixtures("setup_credentials")


@pytest.mark.usefixtures("mock_token_hex", "mock_yoto_client")
async def test_entity_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Snapshot the media player entity state."""
    freezer.move_to("2026-05-08T12:00:00+00:00")
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_MEDIA_PLAY, "resume"),
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_STOP, "stop"),
        (SERVICE_MEDIA_NEXT_TRACK, "next_track"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "previous_track"),
    ],
)
async def test_playback_commands(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Playback service calls reach the client."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    getattr(mock_yoto_client, method).assert_called_once_with("player-test")


async def test_set_volume(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Volume is forwarded as an integer 0-100."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )

    mock_yoto_client.set_volume.assert_called_once_with("player-test", 50)


async def test_seek(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Seek delegates to the client with the integer position."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_SEEK_POSITION: 30},
        blocking=True,
    )

    mock_yoto_client.seek.assert_called_once_with("player-test", 30)


async def test_state_unavailable_when_offline(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """When the player reports offline the entity is unavailable."""
    player = next(iter(mock_yoto_client.players.values()))
    player.status.is_online = False

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_no_card_metadata_when_card_id_missing(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Card metadata properties return None when no card is active."""
    player = next(iter(mock_yoto_client.players.values()))
    player.last_event.card_id = None

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert "media_album_name" not in state.attributes
    assert "media_artist" not in state.attributes
    assert "entity_picture" not in state.attributes


async def test_state_idle_before_first_event(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A freshly-online player with no playback event yet reports IDLE."""
    player = next(iter(mock_yoto_client.players.values()))
    player.last_event.playback_status = None

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "idle"


async def test_command_error_raises(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Yoto command failures surface as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)
    mock_yoto_client.pause.side_effect = YotoError("nope")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
