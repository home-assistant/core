"""Test the MusicCast media player: browsing and playing media."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaClass,
    MediaType,
)
from homeassistant.components.yamaha_musiccast.const import DEFAULT_ZONE, DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import STATIONS, TEST_DEVICE_ID


@pytest.fixture
def platforms() -> list[Platform]:
    """Load only the media player platform."""
    return [Platform.MEDIA_PLAYER]


@pytest.fixture
def zone_power() -> str:
    """Power state of the main zone."""
    return "on"


@pytest.fixture
async def media_dir(hass: HomeAssistant) -> None:
    """Set up media sources with the test media folder.

    It has test.mp3, a video, an image and a text file.
    """
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )
    assert await async_setup_component(hass, "media_source", {})


@pytest.fixture
async def entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_musiccast_device: MagicMock,
    platforms: list[Platform],
    zone_power: str,
) -> str:
    """Set up the integration and return the main zone's player."""
    mock_musiccast_device.data.zones[DEFAULT_ZONE].power = zone_power
    mock_config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.yamaha_musiccast.PLATFORMS", platforms),
        # The artwork URL contains the entity access token.
        patch("secrets.token_hex", return_value="mock_token"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        MEDIA_PLAYER_DOMAIN, DOMAIN, f"{TEST_DEVICE_ID}_{DEFAULT_ZONE}"
    )
    assert entity_id
    return entity_id


async def _browse(
    hass_ws_client: WebSocketGenerator, entity_id: str, content_id: str | None = None
) -> dict:
    """Browse media through the websocket API and return the response."""
    client = await hass_ws_client()
    message = {"id": 1, "type": "media_player/browse_media", "entity_id": entity_id}
    if content_id is not None:
        message["media_content_id"] = content_id
        message["media_content_type"] = MediaType.MUSIC
    await client.send_json(message)
    return await client.receive_json()


async def _play(hass: HomeAssistant, entity_id: str, content_id: str) -> None:
    """Play media through the media player service."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_CONTENT_ID: content_id,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
        },
        blocking=True,
    )


def _list_fields(content_id: str) -> list[str]:
    """Return the fields of a list content id that Home Assistant reads.

    Type, input, menu layer and index; the library may add more fields.
    """
    return content_id.split(":")[:4]


def _children(result: dict) -> list[tuple[str, str, bool, bool]]:
    """Title, content id, can_play and can_expand of the browsed children."""
    return [
        (
            child["title"],
            child["media_content_id"],
            child["can_play"],
            child["can_expand"],
        )
        for child in result["children"]
    ]


@pytest.mark.usefixtures("entity_id")
async def test_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the state and attributes of the media players."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_browse_media_root(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entity_id: str
) -> None:
    """Test the root lists presets and the browsable inputs of the zone."""
    response = await _browse(hass_ws_client, entity_id)

    assert response["success"]
    result = response["result"]
    assert result["title"] == "Library"
    assert result["can_expand"]
    # Bluetooth is an input of the zone, but it can't be browsed.
    assert _children(result) == [
        ("Presets", "presets", False, True),
        ("NET RADIO", "input:net_radio", False, True),
    ]
    assert {child["media_class"] for child in result["children"]} == {
        MediaClass.DIRECTORY
    }


@pytest.mark.usefixtures("media_dir")
async def test_browse_media_root_with_media_sources(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entity_id: str
) -> None:
    """Test the media sources follow the MusicCast entries at the root."""
    response = await _browse(hass_ws_client, entity_id)

    assert response["success"]
    assert _children(response["result"]) == [
        ("Presets", "presets", False, True),
        ("NET RADIO", "input:net_radio", False, True),
        # The only media folder is shown directly.
        ("media", "media-source://media_source/local/.", False, True),
    ]


async def test_browse_media_presets(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entity_id: str
) -> None:
    """Test browsing the presets of the device."""
    response = await _browse(hass_ws_client, entity_id, "presets")

    assert response["success"]
    result = response["result"]
    assert result["title"] == "Presets"
    assert _children(result) == [
        ("net_radio - My Station", "presets:1", True, False),
        ("server - Album", "presets:3", True, False),
    ]
    assert {child["media_class"] for child in result["children"]} == {MediaClass.TRACK}


async def test_browse_media_input(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    mock_musiccast_device: MagicMock,
) -> None:
    """Test an input opens its root menu, wherever the list cursor was."""
    mock_musiccast_device.list_menu.path = ["1", "0"]

    response = await _browse(hass_ws_client, entity_id, "input:net_radio")

    assert response["success"]
    assert mock_musiccast_device.return_in_list.await_count == 2
    result = response["result"]
    assert result["title"] == "Net Radio"
    assert _list_fields(result["media_content_id"]) == ["list", "net_radio", "0", "<>0"]
    assert [
        (child["title"], _list_fields(child["media_content_id"]), child["can_expand"])
        for child in result["children"]
    ] == [
        ("Favorites", ["list", "net_radio", "1", "0"], True),
        ("Countries", ["list", "net_radio", "1", "1"], True),
    ]
    assert result["children"][0]["thumbnail"] == (
        "http://127.0.0.1/thumb/Favorites.png"
    )


async def test_browse_media_folder_and_pages(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    mock_musiccast_device: MagicMock,
) -> None:
    """Test opening a folder of the list and its next page."""
    response = await _browse(hass_ws_client, entity_id, "list:net_radio:1:0")

    assert response["success"]
    mock_musiccast_device.select_list_item.assert_awaited_once_with("0", DEFAULT_ZONE)
    result = response["result"]
    assert result["title"] == "Favorites"
    # A page has 24 entries; the device returns them 8 at a time.
    assert _children(result) == [
        *(
            (station, f"list:net_radio:2:{index}", True, False)
            for index, station in enumerate(STATIONS[:24])
        ),
        ("Next Page", "list:net_radio:1:<>24", False, True),
    ]
    assert result["children"][0]["media_class"] == MediaClass.TRACK
    assert result["children"][-1]["media_class"] == MediaClass.DIRECTORY

    response = await _browse(hass_ws_client, entity_id, "list:net_radio:1:<>24")

    assert response["success"]
    assert _children(response["result"]) == [
        (station, f"list:net_radio:2:{index}", True, False)
        for index, station in enumerate(STATIONS[24:], start=24)
    ]
    # Turning the page doesn't select anything.
    mock_musiccast_device.select_list_item.assert_awaited_once()


async def test_browse_media_parent_folder(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    mock_musiccast_device: MagicMock,
) -> None:
    """Test browsing a folder above the list cursor goes back up to it."""
    mock_musiccast_device.list_menu.path = ["1", "0"]

    response = await _browse(hass_ws_client, entity_id, "list:net_radio:1:1")

    assert response["success"]
    mock_musiccast_device.return_in_list.assert_awaited_once_with(DEFAULT_ZONE)
    mock_musiccast_device.select_list_item.assert_not_awaited()
    result = response["result"]
    assert result["title"] == "Countries"
    assert _children(result) == [("Poland", "list:net_radio:2:0", False, True)]


@pytest.mark.usefixtures("media_dir")
async def test_browse_media_source(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entity_id: str
) -> None:
    """Test media sources are browsed, with audio files only."""
    response = await _browse(
        hass_ws_client, entity_id, "media-source://media_source/local/."
    )

    assert response["success"]
    assert [
        (child["title"], child["media_content_id"])
        for child in response["result"]["children"]
    ] == [("test.mp3", "media-source://media_source/local/test.mp3")]


@pytest.mark.parametrize("zone_power", ["standby"])
async def test_browse_media_turned_off(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    mock_musiccast_device: MagicMock,
) -> None:
    """Test a zone that is off doesn't offer browsing."""
    assert hass.states.get(entity_id).state == "off"

    response = await _browse(hass_ws_client, entity_id, "input:net_radio")

    assert not response["success"]
    assert response["error"]["message"] == "Player does not support browsing media"
    mock_musiccast_device.get_list_info.assert_not_awaited()


@pytest.mark.parametrize(
    ("content_id", "index"),
    [
        pytest.param("list:net_radio:2:5", "5", id="entry"),
        # The list itself (index -1) plays from its first entry.
        pytest.param("list:net_radio:2:-1", "0", id="whole_list"),
    ],
)
async def test_play_list_entry(
    hass: HomeAssistant,
    entity_id: str,
    mock_musiccast_device: MagicMock,
    content_id: str,
    index: str,
) -> None:
    """Test playing an entry of the device list."""
    await _play(hass, entity_id, content_id)

    mock_musiccast_device.play_list_media.assert_awaited_once_with(index, DEFAULT_ZONE)
    mock_musiccast_device.turn_on.assert_not_awaited()


async def test_play_browsed_entry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    mock_musiccast_device: MagicMock,
) -> None:
    """Test browsing from an input to an entry and playing it."""
    response = await _browse(hass_ws_client, entity_id, "input:net_radio")
    folder = response["result"]["children"][0]
    assert folder["title"] == "Favorites"

    response = await _browse(hass_ws_client, entity_id, folder["media_content_id"])
    assert response["result"]["title"] == "Favorites"
    entry = response["result"]["children"][5]
    assert entry["title"] == "Station 5"

    await _play(hass, entity_id, entry["media_content_id"])

    mock_musiccast_device.play_list_media.assert_awaited_once_with("5", DEFAULT_ZONE)


async def test_play_preset(
    hass: HomeAssistant, entity_id: str, mock_musiccast_device: MagicMock
) -> None:
    """Test recalling a preset."""
    await _play(hass, entity_id, "presets:3")

    mock_musiccast_device.recall_netusb_preset.assert_awaited_once_with(
        DEFAULT_ZONE, "3"
    )


@pytest.mark.parametrize(
    ("content_id", "url"),
    [
        pytest.param(
            "https://example.com/stream.mp3",
            "https://example.com/stream.mp3",
            id="absolute",
        ),
        pytest.param(
            "/local/song.mp3", "http://example.local:8123/local/song.mp3", id="relative"
        ),
    ],
)
async def test_play_url(
    hass: HomeAssistant,
    entity_id: str,
    mock_musiccast_device: MagicMock,
    content_id: str,
    url: str,
) -> None:
    """Test playing a URL; relative URLs get Home Assistant's address."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )

    await _play(hass, entity_id, content_id)

    mock_musiccast_device.play_url_media.assert_awaited_once_with(
        DEFAULT_ZONE, url, "HomeAssistant"
    )


@pytest.mark.usefixtures("media_dir")
async def test_play_media_source(
    hass: HomeAssistant, entity_id: str, mock_musiccast_device: MagicMock
) -> None:
    """Test a media source item is played by its signed URL."""
    await _play(hass, entity_id, "media-source://media_source/local/test.mp3")

    mock_musiccast_device.play_url_media.assert_awaited_once()
    zone, url, title = mock_musiccast_device.play_url_media.await_args.args
    assert zone == DEFAULT_ZONE
    assert url.startswith("http://example.local:8123/media/local/test.mp3?authSig=")
    assert title == "HomeAssistant"


@pytest.mark.parametrize("zone_power", ["standby"])
async def test_play_media_turns_on(
    hass: HomeAssistant, entity_id: str, mock_musiccast_device: MagicMock
) -> None:
    """Test a zone that is off is turned on before it plays."""
    calls = AsyncMock()
    calls.attach_mock(mock_musiccast_device.turn_on, "turn_on")
    calls.attach_mock(mock_musiccast_device.recall_netusb_preset, "recall")

    await _play(hass, entity_id, "presets:1")

    assert calls.mock_calls == [
        call.turn_on(DEFAULT_ZONE),
        call.recall(DEFAULT_ZONE, "1"),
    ]


async def test_play_unsupported_media(
    hass: HomeAssistant, entity_id: str, mock_musiccast_device: MagicMock
) -> None:
    """Test other content ids are refused."""
    with pytest.raises(
        HomeAssistantError,
        match="Only presets, media from media browser and http URLs are supported",
    ):
        await _play(hass, entity_id, "spotify:track:1234")

    mock_musiccast_device.play_list_media.assert_not_awaited()
    mock_musiccast_device.recall_netusb_preset.assert_not_awaited()
    mock_musiccast_device.play_url_media.assert_not_awaited()
