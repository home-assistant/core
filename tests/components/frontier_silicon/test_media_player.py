"""Tests for the Frontier Silicon media player."""

from unittest.mock import AsyncMock, patch

from afsapi import PlayState
import pytest

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_afsapi() -> AsyncMock:
    """Create a mock AFSAPI device in playing state."""
    mock = AsyncMock()
    mock.get_power.return_value = True
    mock.get_play_status.return_value = PlayState.PLAYING
    mock.get_modes.return_value = []
    mock.get_equalisers.return_value = []
    mock.get_volume_steps.return_value = 41
    mock.get_play_name.return_value = "Station Name"
    mock.get_play_text.return_value = "Now Playing"
    mock.get_play_artist.return_value = "Artist"
    mock.get_play_album.return_value = "Album"
    mock.get_mode.return_value = None
    mock.get_mute.return_value = False
    mock.get_play_graphic.return_value = "http://example.com/image.png"
    mock.get_eq_preset.return_value = None
    mock.get_volume.return_value = 20
    return mock


async def _setup_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
) -> None:
    """Set up the frontier_silicon integration with a mock AFSAPI."""
    with patch(
        "homeassistant.components.frontier_silicon.AFSAPI",
        return_value=mock_afsapi,
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_update_normal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
) -> None:
    """Test normal update with valid text metadata."""
    await _setup_entity(hass, config_entry, mock_afsapi)

    state = hass.states.get("media_player.mock_title")
    assert state is not None
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes["media_title"] == "Station Name - Now Playing"
    assert state.attributes["media_artist"] == "Artist"
    assert state.attributes["media_album_name"] == "Album"
    assert state.attributes["entity_picture"] is not None


@pytest.mark.parametrize(
    ("method", "attribute", "expected_value"),
    [
        ("get_play_name", "media_title", "Now Playing"),
        ("get_play_text", "media_title", "Station Name"),
        ("get_play_artist", "media_artist", None),
        ("get_play_album", "media_album_name", None),
        ("get_play_graphic", "entity_picture", None),
    ],
)
async def test_update_unicode_decode_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
    method: str,
    attribute: str,
    expected_value: str | None,
) -> None:
    """Test that UnicodeDecodeError on a metadata call is handled gracefully."""
    getattr(mock_afsapi, method).side_effect = UnicodeDecodeError(
        "utf-8", b"\xc3", 0, 1, "invalid continuation byte"
    )

    await _setup_entity(hass, config_entry, mock_afsapi)

    state = hass.states.get("media_player.mock_title")
    assert state is not None
    assert state.state == MediaPlayerState.PLAYING

    if attribute == "media_title":
        assert state.attributes["media_title"] == expected_value
    else:
        assert state.attributes.get(attribute) is expected_value
