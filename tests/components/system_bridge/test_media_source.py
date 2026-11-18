"""Test the System Bridge integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths
from systembridgeconnector.exceptions import (
    AuthenticationException,
    BadRequestException,
    ConnectionErrorException,
)

from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source import (
    DOMAIN as MEDIA_SOURCE_DOMAIN,
    URI_SCHEME,
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import FIXTURE_USER_INPUT


def _signed_url(base: str, path: str) -> str:
    """Return a URL as System Bridge signs one for a file."""
    return (
        f"http://127.0.0.1:9170/api/media/file/data?base={base}&path={path}"
        "&expires=1794771735&sig=signed"
    )


@pytest.fixture(autouse=True)
def mock_media_file_url() -> Generator[AsyncMock]:
    """Have System Bridge sign media file URLs."""
    with patch(
        "homeassistant.components.system_bridge.media_source.HTTPClient.media_file_url",
        AsyncMock(side_effect=_signed_url),
    ) as mock_media_file_url:
        yield mock_media_file_url


@pytest.fixture(autouse=True)
async def setup_component(hass: HomeAssistant) -> None:
    """Set up component."""
    assert await async_setup_component(
        hass,
        MEDIA_SOURCE_DOMAIN,
        {},
    )


async def test_root(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test root media browsing."""
    browse_media_root = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}",
    )

    assert browse_media_root.as_dict() == snapshot(
        name=f"{DOMAIN}_media_source_root",
        exclude=paths("children", "media_content_id"),
    )


async def test_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test browsing entry."""
    browse_media_entry = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{init_integration.entry_id}",
    )

    assert browse_media_entry.as_dict() == snapshot(
        name=f"{DOMAIN}_media_source_entry",
        exclude=paths("children", "media_content_id"),
    )


async def test_directory(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test browsing directory."""
    browse_media_directory = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{init_integration.entry_id}~~documents",
    )

    assert browse_media_directory.as_dict() == snapshot(
        name=f"{DOMAIN}_media_source_directory",
        exclude=paths("children", "media_content_id"),
    )


async def test_directory_children_content_type(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test subdirectories have a string media content type."""
    browse_media_directory = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{init_integration.entry_id}~~documents",
    )

    assert [
        (child.title, child.media_content_type)
        for child in browse_media_directory.children
    ] == [("testsubdirectory", "")]


async def test_subdirectory(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test browsing directory."""
    browse_media_directory = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{init_integration.entry_id}~~documents/testsubdirectory",
    )

    assert browse_media_directory.as_dict() == snapshot(
        name=f"{DOMAIN}_media_source_subdirectory",
        exclude=paths("children", "media_content_id"),
    )


async def test_file(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test browsing file."""
    resolve_media_file = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{init_integration.entry_id}~~documents/testfile.txt~~text/plain",
        None,
    )

    assert resolve_media_file == snapshot(
        name=f"{DOMAIN}_media_source_file_text",
    )

    resolve_media_file = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{init_integration.entry_id}~~documents/testimage.jpg~~image/jpeg",
        None,
    )

    assert resolve_media_file == snapshot(
        name=f"{DOMAIN}_media_source_file_image",
    )


async def test_file_url_signed_by_system_bridge(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_media_file_url: AsyncMock,
) -> None:
    """Test a file's URL is the one System Bridge signs, without the key."""
    resolved = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{init_integration.entry_id}~~documents/my file.txt~~text/plain",
        None,
    )

    mock_media_file_url.assert_awaited_once_with("documents", "my file.txt")
    assert resolved.url == _signed_url("documents", "my file.txt")
    assert FIXTURE_USER_INPUT[CONF_TOKEN] not in resolved.url


@pytest.mark.parametrize(
    "side_effect",
    [AuthenticationException, BadRequestException, ConnectionErrorException],
)
async def test_file_url_failed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_media_file_url: AsyncMock,
    side_effect: type[Exception],
) -> None:
    """Test a file System Bridge won't sign a URL for can't be resolved."""
    mock_media_file_url.side_effect = side_effect

    with pytest.raises(Unresolvable):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{init_integration.entry_id}~~documents/my file.txt~~text/plain",
            None,
        )


@pytest.mark.parametrize(
    "entry_id",
    [
        pytest.param("badentryid", id="not_found"),
        pytest.param("other_entry", id="other_integration"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_bad_entry(hass: HomeAssistant, entry_id: str) -> None:
    """Test invalid entry raises BrowseError."""
    MockConfigEntry(
        domain="other", entry_id="other_entry", state=ConfigEntryState.LOADED
    ).add_to_hass(hass)

    with pytest.raises(BrowseError):
        await async_browse_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{entry_id}",
        )

    with pytest.raises(BrowseError):
        await async_browse_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{entry_id}~~baddirectory",
        )

    with pytest.raises(Unresolvable):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{entry_id}~~baddirectory/badfile.txt~~text/plain",
            None,
        )
