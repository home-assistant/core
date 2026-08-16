"""Tests for the Openhome media player platform."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from async_upnp_client.client import UpnpError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.media_player import SCAN_INTERVAL
from homeassistant.components.openhome.const import DOMAIN
from homeassistant.const import CONF_HOST, STATE_PLAYING, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

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


async def _trigger_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance time to trigger the platform polling update naturally."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test the entity stays available after a successful update."""
    await setup_integration(hass, _mock_device())

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_PLAYING

    await _trigger_update(hass, freezer)

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
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    message: str,
) -> None:
    """Test the entity goes unavailable and logs the error on failure."""
    device = _mock_device()
    device.transport_state = AsyncMock(side_effect=exc)
    await setup_integration(hass, device)

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.openhome"):
        await _trigger_update(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE
    assert f"Error updating {ENTITY_ID}" in caplog.text
    assert message in caplog.text
    error_records = [
        record
        for record in caplog.records
        if record.name.startswith("homeassistant.components.openhome")
        and "Error updating" in record.getMessage()
    ]
    assert error_records
    assert error_records[-1].levelno == logging.DEBUG
    assert error_records[-1].exc_info is not None


async def test_async_update_recovers(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the entity recovers after a failed update."""
    device = _mock_device()
    await setup_integration(hass, device)

    device.transport_state = AsyncMock(side_effect=UpnpError("device down"))
    await _trigger_update(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    device.transport_state = AsyncMock(return_value="Playing")
    await _trigger_update(hass, freezer)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_PLAYING
    assert state.attributes["source"] == "Radio"
