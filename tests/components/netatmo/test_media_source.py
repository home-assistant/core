"""Test Local Media Source."""

import ast
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source import (
    DOMAIN as MS_DOMAIN,
    URI_SCHEME,
    PlayMedia,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.components.netatmo.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import selected_platforms

from tests.common import MockConfigEntry, async_load_fixture


async def test_async_browse_media(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test browse media."""
    with selected_platforms([Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Prepare cached Netatmo event data
    data_handler = config_entry.runtime_data
    data_handler.events = ast.literal_eval(
        await async_load_fixture(hass, "events.txt", DOMAIN)
    )
    data_handler.cameras = {
        "12:34:56:78:90:ab": "MyCamera",
        "12:34:56:78:90:ac": "MyOutdoorCamera",
    }

    assert await async_setup_component(hass, MS_DOMAIN, {})
    await hass.async_block_till_done()

    # Test camera not exists
    with pytest.raises(BrowseError) as excinfo:
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/events/98:76:54:32:10:ff")
    assert str(excinfo.value) == "Camera does not exist."

    # Test browse event
    with pytest.raises(BrowseError) as excinfo:
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/events/12:34:56:78:90:ab/12345"
        )
    assert str(excinfo.value) == "Event does not exist."

    # Test invalid base
    with pytest.raises(BrowseError) as excinfo:
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/invalid/base")
    assert str(excinfo.value) == "Unknown source directory."

    # Test invalid base
    with pytest.raises(BrowseError) as excinfo:
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/")
    assert str(excinfo.value) == (
        "Failed to browse media with content ID media-source://netatmo/: "
        "Invalid media source URI"
    )
    # Test successful listing
    media = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/events")

    # Test successful listing
    media = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/events/")

    # Test successful events listing
    media = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/events/12:34:56:78:90:ab"
    )

    # Test successful event listing
    media = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/events/12:34:56:78:90:ab/1654191519"
    )
    assert media

    # Test successful event resolve
    media = await async_resolve_media(
        hass, f"{URI_SCHEME}{DOMAIN}/events/12:34:56:78:90:ab/1654191519", None
    )
    assert media == PlayMedia(
        url="http:///files/high/index.m3u8", mime_type="application/x-mpegURL"
    )
