"""Tests for the Openhome media player platform."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from async_upnp_client.client import UpnpError

from homeassistant.components.media_player import DATA_COMPONENT
from homeassistant.components.openhome.const import DOMAIN
from homeassistant.const import CONF_HOST, STATE_PLAYING, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "media_player.friendly_name"

TRACK_INFO = {
    "albumArtwork": "http://artwork",
    "albumTitle": "Album",
    "title": "Title",
    "artist": ["Artist"],
}

SOURCES = [
    {"name": "Radio", "index": 1, "type": "Radio"},
    {"name": "Playlist", "index": 2, "type": "Playlist"},
]


def _mock_device() -> MagicMock:
    """Create a mocked Openhome device."""
    device = MagicMock()
    device.init = AsyncMock()
    device.uuid = MagicMock(return_value="uuid")
    device.manufacturer = MagicMock(return_value="manufacturer")
    device.model_name = MagicMock(return_value="model_name")
    device.friendly_name = MagicMock(return_value="friendly_name")
    device.room = AsyncMock(return_value="friendly_name")
    device.track_info = AsyncMock(return_value=TRACK_INFO)
    device.volume_enabled = True
    device.volume = AsyncMock(return_value=50)
    device.is_muted = AsyncMock(return_value=False)
    device.sources = AsyncMock(return_value=SOURCES)
    device.source = AsyncMock(return_value={"name": "Radio", "type": "Radio"})
    device.is_in_standby = AsyncMock(return_value=False)
    device.transport_state = AsyncMock(return_value="Playing")
    return device


async def setup_integration(hass: HomeAssistant, device: MagicMock) -> None:
    """Load the openhome media player platform with a mocked device."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "http://localhost"})
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.openhome.PLATFORMS", [Platform.MEDIA_PLAYER]),
        patch("homeassistant.components.openhome.Device", return_value=device),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def _async_update_entity(hass: HomeAssistant) -> None:
    """Force an update of the media player entity."""
    entity = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert entity is not None
    await entity.async_update()
    entity.async_write_ha_state()


async def test_setup(hass: HomeAssistant) -> None:
    """Test the entity stays available after a successful update."""
    await setup_integration(hass, _mock_device())

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_PLAYING

    await _async_update_entity(hass)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_PLAYING
    assert state.attributes["media_title"] == "Title"
    assert state.attributes["media_artist"] == "Artist"
    assert state.attributes["source"] == "Radio"
    assert state.attributes["volume_level"] == 0.5


@pytest.mark.parametrize(
    ("exc", "message"),
    [
        pytest.param(UpnpError("upnp error"), "upnp error", id="upnp_error"),
        pytest.param(TimeoutError("timeout"), "timeout", id="timeout_error"),
        pytest.param(
            aiohttp.ClientError("client error"), "client error", id="client_error"
        ),
    ],
)
async def test_async_update_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    message: str,
) -> None:
    """Test the entity goes unavailable and logs the error on failure."""
    device = _mock_device()
    device.transport_state = AsyncMock(side_effect=exc)
    await setup_integration(hass, device)

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.openhome"):
        await _async_update_entity(hass)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE
    assert f"Error updating {ENTITY_ID}" in caplog.text
    assert message in caplog.text


async def test_async_update_recovers(hass: HomeAssistant) -> None:
    """Test the entity recovers after a failed update."""
    device = _mock_device()
    await setup_integration(hass, device)

    # First update fails and the entity becomes unavailable
    device.transport_state = AsyncMock(side_effect=UpnpError("device down"))
    await _async_update_entity(hass)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # Second update succeeds and the entity recovers
    device.transport_state = AsyncMock(return_value="Playing")
    await _async_update_entity(hass)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_PLAYING
    assert state.attributes["source"] == "Radio"
