"""Tests for the Jellyfin media_player platform."""
from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.components.media_player import (
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_SEASON,
    ATTR_MEDIA_SERIES_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    MediaClass,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


async def test_media_player(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test the Jellyfin media player."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    state = hass.states.get("media_player.jellyfin_device")

    assert state
    assert state.state == MediaPlayerState.PAUSED
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "JELLYFIN-DEVICE"
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 0.0
    assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is True
    assert state.attributes.get(ATTR_MEDIA_DURATION) == 60
    assert state.attributes.get(ATTR_MEDIA_POSITION) == 10
    assert state.attributes.get(ATTR_MEDIA_POSITION_UPDATED_AT)
    assert state.attributes.get(ATTR_MEDIA_CONTENT_ID) == "EPISODE-UUID"
    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MediaType.TVSHOW
    assert state.attributes.get(ATTR_MEDIA_SERIES_TITLE) == "SERIES"
    assert state.attributes.get(ATTR_MEDIA_SEASON) == 1
    assert state.attributes.get(ATTR_MEDIA_EPISODE) == 3

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.entity_category is None
    assert entry.unique_id == "SERVER-UUID-SESSION-UUID"

    assert len(mock_api.sessions.mock_calls) == 1
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(mock_api.sessions.mock_calls) == 2

    mock_api.sessions.return_value = []
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()
    assert len(mock_api.sessions.mock_calls) == 3

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.connections == set()
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "DEVICE-UUID")}
    assert device.manufacturer == "Jellyfin"
    assert device.name == "JELLYFIN-DEVICE"
    assert device.sw_version == "1.0.0"


async def test_media_player_music(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test the Jellyfin media player."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("media_player.jellyfin_device_four")

    assert state
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "JELLYFIN DEVICE FOUR"
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 1.0
    assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is False
    assert state.attributes.get(ATTR_MEDIA_DURATION) == 73
    assert state.attributes.get(ATTR_MEDIA_POSITION) == 22
    assert state.attributes.get(ATTR_MEDIA_POSITION_UPDATED_AT)
    assert state.attributes.get(ATTR_MEDIA_CONTENT_ID) == "MUSIC-UUID"
    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MediaType.MUSIC
    assert state.attributes.get(ATTR_MEDIA_ALBUM_NAME) == "ALBUM"
    assert state.attributes.get(ATTR_MEDIA_ALBUM_ARTIST) == "Album Artist"
    assert state.attributes.get(ATTR_MEDIA_ARTIST) == "Contributing Artist"
    assert state.attributes.get(ATTR_MEDIA_TRACK) == 1
    assert state.attributes.get(ATTR_MEDIA_SERIES_TITLE) is None
    assert state.attributes.get(ATTR_MEDIA_SEASON) is None
    assert state.attributes.get(ATTR_MEDIA_EPISODE) is None

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id is None
    assert entry.entity_category is None
    assert entry.unique_id == "SERVER-UUID-SESSION-UUID-FOUR"


async def test_services(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test Jellyfin media player services."""
    state = hass.states.get("media_player.jellyfin_device")
    assert state

    await hass.services.async_call(
        MP_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: state.entity_id,
            "media_content_type": "",
            "media_content_id": "ITEM-UUID",
        },
        blocking=True,
    )
    assert len(mock_api.remote_play_media.mock_calls) == 1
    assert mock_api.remote_play_media.mock_calls[0].args == (
        "SESSION-UUID",
        ["ITEM-UUID"],
    )

    await hass.services.async_call(
        MP_DOMAIN,
        "media_pause",
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )
    assert len(mock_api.remote_pause.mock_calls) == 1

    await hass.services.async_call(
        MP_DOMAIN,
        "media_play",
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )
    assert len(mock_api.remote_unpause.mock_calls) == 1

    await hass.services.async_call(
        MP_DOMAIN,
        "media_play_pause",
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )
    assert len(mock_api.remote_playpause.mock_calls) == 1

    await hass.services.async_call(
        MP_DOMAIN,
        "media_seek",
        {
            ATTR_ENTITY_ID: state.entity_id,
            "seek_position": 10,
        },
        blocking=True,
    )
    assert len(mock_api.remote_seek.mock_calls) == 1
    assert mock_api.remote_seek.mock_calls[0].args == (
        "SESSION-UUID",
        100000000,
    )

    await hass.services.async_call(
        MP_DOMAIN,
        "media_stop",
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )
    assert len(mock_api.remote_stop.mock_calls) == 1

    await hass.services.async_call(
        MP_DOMAIN,
        "volume_set",
        {
            ATTR_ENTITY_ID: state.entity_id,
            "volume_level": 0.5,
        },
        blocking=True,
    )
    assert len(mock_api.remote_set_volume.mock_calls) == 1

    await hass.services.async_call(
        MP_DOMAIN,
        "volume_mute",
        {
            ATTR_ENTITY_ID: state.entity_id,
            "is_volume_muted": True,
        },
        blocking=True,
    )
    assert len(mock_api.remote_mute.mock_calls) == 1

    await hass.services.async_call(
        MP_DOMAIN,
        "volume_mute",
        {
            ATTR_ENTITY_ID: state.entity_id,
            "is_volume_muted": False,
        },
        blocking=True,
    )
    assert len(mock_api.remote_unmute.mock_calls) == 1


async def test_browse_media(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_api: MagicMock,
) -> None:
    """Test Jellyfin browse media."""
    client = await hass_ws_client()

    # browse root folder
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.jellyfin_device",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_child_item = {
        "title": "COLLECTION FOLDER",
        "media_class": MediaClass.DIRECTORY.value,
        "media_content_type": "collection",
        "media_content_id": "COLLECTION-FOLDER-UUID",
        "can_play": False,
        "can_expand": True,
        "thumbnail": "http://localhost/Items/c22fd826-17fc-44f4-9b04-1eb3e8fb9173/Images/Backdrop.jpg",
        "children_media_class": None,
    }

    assert response["result"]["media_content_id"] == ""
    assert response["result"]["media_content_type"] == "root"
    assert response["result"]["title"] == "Jellyfin"
    assert response["result"]["children"][0] == expected_child_item

    # browse collection folder
    await client.send_json(
        {
            "id": 2,
            "type": "media_player/browse_media",
            "entity_id": "media_player.jellyfin_device",
            "media_content_type": "collection",
            "media_content_id": "COLLECTION-FOLDER-UUID",
        }
    )

    response = await client.receive_json()
    expected_child_item = {
        "title": "EPISODE",
        "media_class": MediaClass.EPISODE.value,
        "media_content_type": MediaType.EPISODE.value,
        "media_content_id": "EPISODE-UUID",
        "can_play": True,
        "can_expand": False,
        "thumbnail": "http://localhost/Items/c22fd826-17fc-44f4-9b04-1eb3e8fb9173/Images/Backdrop.jpg",
        "children_media_class": None,
    }

    assert response["success"]
    assert response["result"]["media_content_id"] == "COLLECTION-FOLDER-UUID"
    assert response["result"]["title"] == "FOLDER"
    assert response["result"]["children"][0] == expected_child_item

    # browse for collection without children
    mock_api.user_items.side_effect = None
    mock_api.user_items.return_value = {}

    await client.send_json(
        {
            "id": 3,
            "type": "media_player/browse_media",
            "entity_id": "media_player.jellyfin_device",
            "media_content_type": "collection",
            "media_content_id": "COLLECTION-FOLDER-UUID",
        }
    )

    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]
    assert (
        response["error"]["message"]
        == "Media not found: collection / COLLECTION-FOLDER-UUID"
    )

    # browse for non-existent item
    mock_api.get_item.side_effect = None
    mock_api.get_item.return_value = {}

    await client.send_json(
        {
            "id": 4,
            "type": "media_player/browse_media",
            "entity_id": "media_player.jellyfin_device",
            "media_content_type": "collection",
            "media_content_id": "COLLECTION-UUID-404",
        }
    )

    response = await client.receive_json()
    assert response["success"] is False
    assert response["error"]
    assert (
        response["error"]["message"]
        == "Media not found: collection / COLLECTION-UUID-404"
    )
