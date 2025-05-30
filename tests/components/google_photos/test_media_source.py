"""Test the Google Photos media source."""

from unittest.mock import Mock

from google_photos_library_api.exceptions import GooglePhotosApiError
import pytest

from homeassistant.components.google_photos.const import DOMAIN, UPLOAD_SCOPE
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


@pytest.mark.usefixtures("setup_integration", "mock_api")
@pytest.mark.parametrize(
    ("scopes"),
    [
        [UPLOAD_SCOPE],
    ],
)
async def test_no_read_scopes(
    hass: HomeAssistant,
) -> None:
    """Test a media source with only write scopes configured so no media source exists."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Google Photos"
    assert not browse.children


@pytest.mark.usefixtures("setup_integration", "mock_api")
@pytest.mark.parametrize(
    ("album_path", "expected_album_title"),
    [
        (f"{CONFIG_ENTRY_ID}/a/album-media-id-1", "Album title"),
    ],
)
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
async def test_browse_albums(
    hass: HomeAssistant,
    album_path: str,
    expected_album_title: str,
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
        (f"{CONFIG_ENTRY_ID}/a/album-media-id-1", "Album title"),
    ]

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/{album_path}")
    assert browse.domain == DOMAIN
    assert browse.identifier == album_path
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


@pytest.mark.usefixtures("setup_integration", "mock_api")
async def test_invalid_config_entry(hass: HomeAssistant) -> None:
    """Test browsing to a config entry that does not exist."""
    with pytest.raises(BrowseError, match="Could not find config entry"):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/invalid-config-entry")


@pytest.mark.usefixtures("setup_integration", "mock_api")
@pytest.mark.parametrize("fixture_name", ["list_mediaitems.json"])
async def test_browse_invalid_path(hass: HomeAssistant) -> None:
    """Test browsing to a photo is not possible."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Google Photos"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (CONFIG_ENTRY_ID, "Account Name")
    ]

    with pytest.raises(BrowseError, match="Unsupported identifier"):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}/p/some-photo-id"
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


@pytest.mark.usefixtures("setup_integration", "mock_api")
async def test_list_media_items_failure(hass: HomeAssistant, mock_api: Mock) -> None:
    """Test browsing to an album id that does not exist."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Google Photos"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (CONFIG_ENTRY_ID, "Account Name")
    ]

    mock_api.list_media_items.side_effect = GooglePhotosApiError("some error")

    with pytest.raises(BrowseError, match="Error listing media items"):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}/a/recent"
        )
