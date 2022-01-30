"""Tests for the jellyfin integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock, patch

from homeassistant.components.jellyfin.const import (
    DATA_CLIENT,
    DOMAIN,
    ITEM_TYPE_ALBUM,
    ITEM_TYPE_ARTIST,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    MOCK_ALBUM,
    MOCK_ALBUM_FOLDER_ID,
    MOCK_ALBUM_ID,
    MOCK_ALBUM_LIBRARY,
    MOCK_ARTIST,
    MOCK_ARTIST_ID,
    MOCK_ARTIST_LIBRARY,
    MOCK_AUTH_TOKEN,
    MOCK_DEVICE_ID,
    MOCK_FOLDER_ID,
    MOCK_INVALID_SOURCE_TRACK,
    MOCK_INVALID_SOURCE_TRACK_ID,
    MOCK_MEDIA_FOLDERS,
    MOCK_MOVIE_ID,
    MOCK_NO_INDEX_ALBUM,
    MOCK_NO_INDEX_ALBUM_ID,
    MOCK_NO_INDEX_TRACK,
    MOCK_NO_INDEX_TRACK_ID,
    MOCK_NO_SOURCE_TRACK,
    MOCK_NO_SOURCE_TRACK_ID,
    MOCK_SUCCESFUL_CONNECTION_STATE,
    MOCK_SUCCESFUL_LOGIN_RESPONSE,
    MOCK_TRACK,
    MOCK_TRACK_ID,
    MOCK_USER_ID,
    MOCK_USER_SETTINGS,
    MOCK_VIDEO,
    MOCK_VIDEO_FOLDER_ID,
    MOCK_VIDEO_LIBRARY,
    TEST_PASSWORD,
    TEST_URL,
    TEST_USERNAME,
)

from tests.common import MockConfigEntry


def create_mock_jellyfin_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Add a test config entry."""
    config_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        title=f"{TEST_URL}",
    )
    config_entry.add_to_hass(hass)
    return config_entry


def _create_mock_jellyfin_api() -> Mock:
    """Create a mock Jellyfin api."""
    api = Mock()
    api.artwork = Mock(side_effect=_artwork)
    api.get_item = Mock(side_effect=_select_return_item)
    api.get_media_folders = Mock(return_value=MOCK_MEDIA_FOLDERS)
    api.get_user_settings = Mock(return_value=MOCK_USER_SETTINGS)
    api.user_items = Mock(side_effect=_select_user_items)

    return api


def _select_return_item(item_id: str) -> dict[str, Any]:
    """Return a mock item based on item id."""
    if item_id == MOCK_FOLDER_ID:
        return MOCK_ARTIST_LIBRARY
    elif item_id == MOCK_ALBUM_FOLDER_ID:
        return MOCK_ALBUM_LIBRARY
    elif item_id == MOCK_VIDEO_FOLDER_ID:
        return MOCK_VIDEO_LIBRARY
    elif item_id == MOCK_ARTIST_ID:
        return MOCK_ARTIST
    elif item_id == MOCK_ALBUM_ID:
        return MOCK_ALBUM
    elif item_id == MOCK_NO_INDEX_ALBUM_ID:
        return MOCK_NO_INDEX_ALBUM
    elif item_id == MOCK_TRACK_ID:
        return MOCK_TRACK
    elif item_id == MOCK_MOVIE_ID:
        return MOCK_VIDEO
    elif item_id == MOCK_NO_SOURCE_TRACK_ID:
        return MOCK_NO_SOURCE_TRACK
    elif item_id == MOCK_INVALID_SOURCE_TRACK_ID:
        return MOCK_INVALID_SOURCE_TRACK
    elif item_id == MOCK_NO_INDEX_TRACK_ID:
        return MOCK_NO_INDEX_TRACK


def _select_user_items(handler: str, params: dict[str:str]) -> dict[str, Any]:
    """Return a list of mock items based on the parent id."""
    if params["ParentId"] == MOCK_FOLDER_ID:
        if params["IncludeItemTypes"] == ITEM_TYPE_ARTIST:
            return {"Items": [MOCK_ARTIST]}
        else:
            return {"Items": []}
    elif params["ParentId"] == MOCK_ALBUM_FOLDER_ID:
        if params["IncludeItemTypes"] == ITEM_TYPE_ALBUM:
            return {"Items": [MOCK_ALBUM]}
        else:
            return {"Items": []}
    elif params["ParentId"] == MOCK_ARTIST_ID:
        return {"Items": [MOCK_ALBUM]}
    elif params["ParentId"] == MOCK_ALBUM_ID:
        return {"Items": [MOCK_TRACK]}
    elif params["ParentId"] == MOCK_NO_INDEX_ALBUM_ID:
        return {"Items": [MOCK_NO_INDEX_TRACK]}


def _artwork(item_id: str, art: str, max_width: int, ext: str = "jpg") -> str:
    """Return the artwork url based on item id."""
    return f"{TEST_URL}/Items/{item_id}/Images/{art}?MaxWidth={max_width}&format={ext}"


def _create_mock_jellyfin_connection_manager(
    connection_side_effect: Any = None, login_side_effect: Any = None
) -> Mock:
    """Return a mock Jellyfin connection manager."""
    connection_manager = Mock()
    if connection_side_effect:
        connection_manager.connect_to_address = Mock(side_effect=connection_side_effect)
    else:
        connection_manager.connect_to_address = Mock(
            return_value=MOCK_SUCCESFUL_CONNECTION_STATE
        )
    if login_side_effect:
        connection_manager.login = Mock(side_effect=login_side_effect)
    else:
        connection_manager.login = Mock(return_value=MOCK_SUCCESFUL_LOGIN_RESPONSE)

    return connection_manager


def create_mock_jellyfin_client(
    connection_side_effect: Any = None, login_side_effect: Any = None
) -> Mock:
    """Create mock Jellyfin client."""
    jellyfin_client = MagicMock()
    jellyfin_client.jellyfin = _create_mock_jellyfin_api()
    jellyfin_client.auth = _create_mock_jellyfin_connection_manager(
        connection_side_effect, login_side_effect
    )
    jellyfin_client.config.data = {
        "auth.user_id": MOCK_USER_ID,
        "app.device_id": MOCK_DEVICE_ID,
        "auth.token": MOCK_AUTH_TOKEN,
        "auth.server": TEST_URL,
    }

    return jellyfin_client


async def setup_mock_jellyfin_config_entry(
    hass: HomeAssistant,
    connection_side_effect: Any = None,
    login_side_effect: Any = None,
) -> ConfigEntry:
    """Create a mock Jellyfin config entry."""

    config_entry = create_mock_jellyfin_config_entry(hass)
    client = create_mock_jellyfin_client(connection_side_effect, login_side_effect)

    with patch(
        "homeassistant.components.jellyfin.create_client",
        return_value=client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    hass.data[DOMAIN][config_entry.entry_id] = {DATA_CLIENT: client}

    return config_entry
