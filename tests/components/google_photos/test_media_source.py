"""Test the Google Photos media source."""

from typing import Any
from unittest.mock import Mock

from googleapiclient.errors import HttpError
from httplib2 import Response
import pytest

from homeassistant.components.google_photos.const import DOMAIN
from homeassistant.components.media_source import (
    URI_SCHEME,
    BrowseError,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import CONFIG_ENTRY_ID

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def setup_components(hass: HomeAssistant) -> None:
    """Fixture to initialize the integration."""
    await async_setup_component(hass, "media_source", {})


@pytest.mark.usefixtures("setup_integration")
async def test_no_config_entries(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a media source with no active config entry."""

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")

    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Google Photos"
    assert browse.can_expand
    assert not browse.children


@pytest.mark.usefixtures("setup_integration", "setup_api")
@pytest.mark.parametrize(
    ("fixture_name", "expected_results", "expected_medias"),
    [
        ("list_mediaitems_empty.json", [], []),
        (
            "list_mediaitems.json",
            [
                (f"{CONFIG_ENTRY_ID}/p/id1", "example1.jpg"),
                (f"{CONFIG_ENTRY_ID}/p/id2", "example2.mp4"),
            ],
            [
                ("http://img.example.com/id1=h2160", "image/jpeg"),
                ("http://img.example.com/id2=dv", "video/mp4"),
            ],
        ),
    ],
)
async def test_recent_items(
    hass: HomeAssistant,
    expected_results: list[tuple[str, str]],
    expected_medias: list[tuple[str, str]],
) -> None:
    """Test a media source with no eligible camera devices."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Google Photos"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (CONFIG_ENTRY_ID, "Account Name")
    ]

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}")
    assert browse.domain == DOMAIN
    assert browse.identifier == CONFIG_ENTRY_ID
    assert browse.title == "Account Name"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (f"{CONFIG_ENTRY_ID}/a/recent", "Recent Photos")
    ]

    browse = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}/a/recent"
    )
    assert browse.domain == DOMAIN
    assert browse.identifier == f"{CONFIG_ENTRY_ID}/a/recent"
    assert browse.title == "Account Name"
    assert [
        (child.identifier, child.title) for child in browse.children
    ] == expected_results

    media = [
        await async_resolve_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{child.identifier}", None
        )
        for child in browse.children
    ]
    assert [
        (play_media.url, play_media.mime_type) for play_media in media
    ] == expected_medias


@pytest.mark.usefixtures("setup_integration", "setup_api")
async def test_invalid_config_entry(hass: HomeAssistant) -> None:
    """Test browsing to a config entry that does not exist."""
    with pytest.raises(BrowseError, match="Could not find config entry"):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/invalid-config-entry")


@pytest.mark.usefixtures("setup_integration", "setup_api")
@pytest.mark.parametrize("fixture_name", ["list_mediaitems.json"])
async def test_invalid_album_id(hass: HomeAssistant) -> None:
    """Test browsing to an album id that does not exist."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Google Photos"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (CONFIG_ENTRY_ID, "Account Name")
    ]

    with pytest.raises(BrowseError, match="Unsupported album"):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}/a/invalid-album-id"
        )


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("identifier", "expected_error"),
    [
        (CONFIG_ENTRY_ID, "not a Photo"),
        ("invalid-config-entry/a/example", "not a Photo"),
        ("invalid-config-entry/q/example", "Could not parse"),
        ("too/many/slashes/in/path", "Invalid identifier"),
    ],
)
async def test_missing_photo_id(
    hass: HomeAssistant, identifier: str, expected_error: str
) -> None:
    """Test parsing an invalid media identifier."""
    with pytest.raises(BrowseError, match=expected_error):
        await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/{identifier}", None)


@pytest.mark.usefixtures("setup_integration", "setup_api")
@pytest.mark.parametrize(
    "side_effect",
    [
        HttpError(Response({"status": "403"}), b""),
    ],
)
async def test_list_media_items_failure(
    hass: HomeAssistant,
    setup_api: Any,
    side_effect: HttpError | Response,
) -> None:
    """Test browsing to an album id that does not exist."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Google Photos"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (CONFIG_ENTRY_ID, "Account Name")
    ]

    setup_api.return_value.mediaItems.return_value.list = Mock()
    setup_api.return_value.mediaItems.return_value.list.return_value.execute.side_effect = side_effect

    with pytest.raises(BrowseError, match="Error listing media items"):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}/a/recent"
        )


@pytest.mark.usefixtures("setup_integration", "setup_api")
@pytest.mark.parametrize(
    "fixture_name",
    [
        "api_not_enabled_response.json",
        "not_dict.json",
    ],
)
async def test_media_items_error_parsing_response(hass: HomeAssistant) -> None:
    """Test browsing to an album id that does not exist."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Google Photos"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (CONFIG_ENTRY_ID, "Account Name")
    ]
    with pytest.raises(BrowseError, match="Error listing media items"):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}/a/recent"
        )
