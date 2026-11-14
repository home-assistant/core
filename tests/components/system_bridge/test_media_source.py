"""Test the System Bridge integration."""

from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
import hashlib
import hmac
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths
from systembridgeconnector.models.fixtures.modules.system import FIXTURE_SYSTEM

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
from homeassistant.util import dt as dt_util

from . import FIXTURE_USER_INPUT


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


@pytest.fixture
def signed_url_backend(mock_websocket_client: MagicMock) -> Generator[None]:
    """Report a backend that accepts signed media URLs."""
    system = replace(FIXTURE_SYSTEM, version="5.25.0")
    mock_websocket_client.get_data.return_value = replace(
        mock_websocket_client.get_data.return_value, system=system
    )
    with patch("tests.components.system_bridge.FIXTURE_SYSTEM", system):
        yield


@pytest.mark.usefixtures("signed_url_backend")
async def test_file_signed_url(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test hosts that accept signed URLs get one, without the API token."""
    earliest = int((dt_util.utcnow() + timedelta(hours=24)).timestamp())
    resolved = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{init_integration.entry_id}~~documents/my file.txt~~text/plain",
        None,
    )
    latest = int((dt_util.utcnow() + timedelta(hours=24)).timestamp())

    url = urlparse(resolved.url)
    query = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == (
        "http://127.0.0.1:9170/api/media/file/data"
    )
    assert "token" not in query
    assert query["base"] == ["documents"]
    assert query["path"] == ["my file.txt"]
    [expires] = query["expires"]
    assert earliest <= int(expires) <= latest
    assert query["sig"] == [
        hmac.new(
            FIXTURE_USER_INPUT[CONF_TOKEN].encode(),
            f"documents\nmy file.txt\n{expires}".encode(),
            hashlib.sha256,
        ).hexdigest()
    ]


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
