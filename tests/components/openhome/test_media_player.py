"""Tests for the Openhome media player platform."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from openhomedevice.exceptions import OpenhomeConnectionError
import pytest

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    MediaType,
)
from homeassistant.components.openhome.const import DOMAIN
from homeassistant.components.openhome.services import (
    ATTR_PIN_INDEX,
    SERVICE_INVOKE_PIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "media_player.friendly_name"

SOURCES = [
    {"index": 0, "name": "Playlist", "type": "Playlist"},
    {"index": 1, "name": "Radio", "type": "Radio"},
]

# Each action, the device coroutine it drives, and a source type that exposes
# the supported feature it is gated behind.
ACTIONS = [
    pytest.param(MEDIA_PLAYER_DOMAIN, SERVICE_TURN_ON, {}, "set_standby", "Playlist"),
    pytest.param(MEDIA_PLAYER_DOMAIN, SERVICE_TURN_OFF, {}, "set_standby", "Playlist"),
    pytest.param(MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_PLAY, {}, "play", "Playlist"),
    pytest.param(MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_PAUSE, {}, "pause", "Playlist"),
    pytest.param(MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_STOP, {}, "stop", "Radio"),
    pytest.param(MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_NEXT_TRACK, {}, "skip", "Playlist"),
    pytest.param(
        MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, {}, "skip", "Playlist"
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_UP, {}, "increase_volume", "Playlist"
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_DOWN, {}, "decrease_volume", "Playlist"
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        "set_volume",
        "Playlist",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: True},
        "set_mute",
        "Playlist",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: "Playlist"},
        "set_source",
        "Playlist",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: "http://localhost/track.flac",
        },
        "play_media",
        "Playlist",
    ),
    pytest.param(
        DOMAIN, SERVICE_INVOKE_PIN, {ATTR_PIN_INDEX: 1}, "invoke_pin", "Playlist"
    ),
]


@pytest.fixture
def mock_device() -> Generator[MagicMock]:
    """Return a mocked Openhome device that polls successfully."""
    with patch("homeassistant.components.openhome.Device", MagicMock()) as mock_class:
        device = mock_class.return_value
        device.init = AsyncMock()
        device.uuid = MagicMock(return_value="uuid")
        device.manufacturer = MagicMock(return_value="manufacturer")
        device.model_name = MagicMock(return_value="model_name")
        device.friendly_name = MagicMock(return_value="friendly_name")
        device.volume_enabled = True
        device.pins_enabled = True
        device.room = AsyncMock(return_value="room")
        device.track_info = AsyncMock(return_value={})
        device.volume = AsyncMock(return_value=50)
        device.is_muted = AsyncMock(return_value=False)
        device.sources = AsyncMock(return_value=SOURCES)
        device.is_in_standby = AsyncMock(return_value=False)
        device.transport_state = AsyncMock(return_value="Playing")
        for action in (
            "set_standby",
            "play",
            "pause",
            "stop",
            "skip",
            "increase_volume",
            "decrease_volume",
            "set_volume",
            "set_mute",
            "set_source",
            "play_media",
            "invoke_pin",
        ):
            setattr(device, action, AsyncMock())
        yield device


async def setup_platform(
    hass: HomeAssistant, mock_device: MagicMock, source_type: str
) -> None:
    """Load the media player platform and poll once to populate features."""
    mock_device.source = AsyncMock(
        return_value={"index": 0, "name": source_type, "type": source_type}
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "http://localhost"}, unique_id="uuid"
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.openhome.PLATFORMS", [Platform.MEDIA_PLAYER]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Supported features are only set once the device has been polled.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("domain", "service", "data", "method", "source_type"), ACTIONS
)
async def test_action_error_is_raised(
    hass: HomeAssistant,
    mock_device: MagicMock,
    domain: str,
    service: str,
    data: dict[str, Any],
    method: str,
    source_type: str,
) -> None:
    """Test every action raises when the device rejects the request."""
    await setup_platform(hass, mock_device, source_type)

    getattr(mock_device, method).side_effect = OpenhomeConnectionError(
        "no route to host"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
        )

    getattr(mock_device, method).assert_awaited()
