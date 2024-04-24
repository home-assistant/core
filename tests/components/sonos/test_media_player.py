"""Tests for the Sonos Media Player platform."""

import logging
from typing import Any

import pytest

from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.media_player.const import SERVICE_SELECT_SOURCE
from homeassistant.components.sonos.const import SOURCE_LINEIN, SOURCE_TV
from homeassistant.components.sonos.media_player import LONG_SERVICE_TIMEOUT
from homeassistant.const import STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    CONNECTION_UPNP,
    DeviceRegistry,
)

from .conftest import SoCoMockFactory


async def test_device_registry(
    hass: HomeAssistant, device_registry: DeviceRegistry, async_autosetup_sonos, soco
) -> None:
    """Test sonos device registered in the device registry."""
    reg_device = device_registry.async_get_device(
        identifiers={("sonos", "RINCON_test")}
    )
    assert reg_device is not None
    assert reg_device.model == "Model Name"
    assert reg_device.sw_version == "13.1"
    assert reg_device.connections == {
        (CONNECTION_NETWORK_MAC, "00:11:22:33:44:55"),
        (CONNECTION_UPNP, "uuid:RINCON_test"),
    }
    assert reg_device.manufacturer == "Sonos"
    assert reg_device.name == "Zone A"
    # Default device provides battery info, area should not be suggested
    assert reg_device.suggested_area is None


async def test_device_registry_not_portable(
    hass: HomeAssistant, device_registry: DeviceRegistry, async_setup_sonos, soco
) -> None:
    """Test non-portable sonos device registered in the device registry to ensure area suggested."""
    soco.get_battery_info.return_value = {}
    await async_setup_sonos()

    reg_device = device_registry.async_get_device(
        identifiers={("sonos", "RINCON_test")}
    )
    assert reg_device is not None
    assert reg_device.suggested_area == "Zone A"


async def test_entity_basic(
    hass: HomeAssistant, async_autosetup_sonos, discover
) -> None:
    """Test basic state and attributes."""
    state = hass.states.get("media_player.zone_a")
    assert state.state == STATE_IDLE
    attributes = state.attributes
    assert attributes["friendly_name"] == "Zone A"
    assert attributes["is_volume_muted"] is False
    assert attributes["volume_level"] == 0.19


class _MockMusicServiceItem:
    """Mocks a Soco MusicServiceItem."""

    def __init__(
        self,
        title: str,
        item_id: str,
        parent_id: str,
        item_class: str,
    ) -> None:
        """Initialize the mock item."""
        self.title = title
        self.item_id = item_id
        self.item_class = item_class
        self.parent_id = parent_id

    def get_uri(self) -> str:
        """Return URI."""
        return self.item_id.replace("S://", "x-file-cifs://")


_mock_playlists = [
    _MockMusicServiceItem(
        "playlist1",
        "S://192.168.1.68/music/iTunes/iTunes%20Music%20Library.xml#GUID_1",
        "A:PLAYLISTS",
        "object.container.playlistContainer",
    ),
    _MockMusicServiceItem(
        "playlist2",
        "S://192.168.1.68/music/iTunes/iTunes%20Music%20Library.xml#GUID_2",
        "A:PLAYLISTS",
        "object.container.playlistContainer",
    ),
]


@pytest.mark.parametrize(
    ("media_content_id", "expected_item_id"),
    [
        (
            _mock_playlists[0].item_id,
            _mock_playlists[0].item_id,
        ),
        (
            f"S:{_mock_playlists[1].title}",
            _mock_playlists[1].item_id,
        ),
    ],
)
async def test_play_media_music_library_playlist(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    discover,
    media_content_id,
    expected_item_id,
) -> None:
    """Test that playlists can be found by id or title."""
    soco_mock = soco_factory.mock_list.get("192.168.42.2")
    soco_mock.music_library.get_playlists.return_value = _mock_playlists

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            "entity_id": "media_player.zone_a",
            "media_content_type": "playlist",
            "media_content_id": media_content_id,
        },
        blocking=True,
    )

    assert soco_mock.clear_queue.call_count == 1
    assert soco_mock.add_to_queue.call_count == 1
    assert soco_mock.add_to_queue.call_args_list[0].args[0].item_id == expected_item_id
    assert soco_mock.play_from_queue.call_count == 1


async def test_play_media_music_library_playlist_dne(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling when attempting to play a non-existent playlist ."""
    media_content_id = "S:nonexistent"
    soco_mock = soco_factory.mock_list.get("192.168.42.2")
    soco_mock.music_library.get_playlists.return_value = _mock_playlists

    with caplog.at_level(logging.ERROR):
        caplog.clear()
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                "entity_id": "media_player.zone_a",
                "media_content_type": "playlist",
                "media_content_id": media_content_id,
            },
            blocking=True,
        )
    assert soco_mock.play_uri.call_count == 0
    assert media_content_id in caplog.text
    assert "playlist" in caplog.text


@pytest.mark.parametrize(
    ("source", "result"),
    [
        (
            SOURCE_LINEIN,
            {
                "switch_to_line_in": 1,
            },
        ),
        (
            SOURCE_TV,
            {
                "switch_to_tv": 1,
            },
        ),
        (
            "James Taylor Radio",
            {
                "play_uri": 1,
                "play_uri_uri": "x-sonosapi-radio:ST%3aetc",
                "play_uri_title": "James Taylor Radio",
            },
        ),
        (
            "66 - Watercolors",
            {
                "play_uri": 1,
                "play_uri_uri": "x-sonosapi-hls:Api%3atune%3aliveAudio%3ajazzcafe%3aetc",
                "play_uri_title": "66 - Watercolors",
            },
        ),
        (
            "1984",
            {
                "add_to_queue": 1,
                "add_to_queue_item_id": "A:ALBUMARTIST/Aerosmith/1984",
                "clear_queue": 1,
                "play_from_queue": 1,
            },
        ),
    ],
)
async def test_select_source(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
    source: str,
    result: dict[str, Any],
) -> None:
    """Test the select_source method with a variety of inputs."""
    soco_mock = soco_factory.mock_list.get("192.168.42.2")

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {
            "entity_id": "media_player.zone_a",
            "source": source,
        },
        blocking=True,
    )

    assert soco_mock.switch_to_line_in.call_count == result.get("switch_to_line_in", 0)
    assert soco_mock.switch_to_tv.call_count == result.get("switch_to_tv", 0)
    assert soco_mock.clear_queue.call_count == result.get("clear_queue", 0)
    if result.get("add_to_queue"):
        assert soco_mock.add_to_queue.call_count == result.get("add_to_queue")
        assert soco_mock.add_to_queue.call_args_list[0].args[0].item_id == result.get(
            "add_to_queue_item_id"
        )
        assert (
            soco_mock.add_to_queue.call_args_list[0].kwargs["timeout"]
            == LONG_SERVICE_TIMEOUT
        )
    if result.get("play_from_queue"):
        assert soco_mock.play_from_queue.call_count == result.get("play_from_queue")
        soco_mock.play_from_queue.assert_called_with(0)
    if result.get("play_uri"):
        assert soco_mock.play_uri.call_count == result.get("play_uri")
        soco_mock.play_uri.assert_called_with(
            result.get("play_uri_uri"),
            title=result.get("play_uri_title"),
            timeout=LONG_SERVICE_TIMEOUT,
        )


async def test_select_source_error(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
    async_autosetup_sonos,
) -> None:
    """Test the select_source method with a variety of inputs."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {
                "entity_id": "media_player.zone_a",
                "source": "invalid_source",
            },
            blocking=True,
        )
