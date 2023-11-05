"""Tests for the Reolink media_source platform."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.media_source import (
    DOMAIN as MEDIA_SOURCE_DOMAIN,
    URI_SCHEME,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.components.reolink.const import DOMAIN
from homeassistant.components.stream import DOMAIN as MEDIA_STREAM_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_FILE_NAME = "20230101000000"
TEST_STREAM = "main"
TEST_CHANNEL = "0"
FILE_ID = f"FILE+<CONF_ID>+{TEST_CHANNEL}+{TEST_STREAM}+{TEST_FILE_NAME}"

TEST_MIME_TYPE = "application/x-mpegURL"
TEST_URL = "http:test_url"


@pytest.fixture(autouse=True)
async def setup_component(hass: HomeAssistant) -> None:
    """Set up component."""
    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    assert await async_setup_component(hass, MEDIA_STREAM_DOMAIN, {})


async def test_resolve(
    hass: HomeAssistant, reolink_connect: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Test resolving Reolink media items."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    reolink_connect.get_vod_source.return_value = (TEST_MIME_TYPE, TEST_URL)

    file_id = FILE_ID.replace("<CONF_ID>", config_entry.entry_id)

    play_media = await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/{file_id}")

    assert play_media.mime_type == TEST_MIME_TYPE


async def test_root(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test browsing the Reolink root."""
    reolink_connect.stream_channels = [int(TEST_CHANNEL)]
    reolink_connect.api_version.return_value = 1

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.CAMERA]):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")

    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == "Reolink"
    assert (
        browse.children[0].identifier == f"CAM+{config_entry.entry_id}+{TEST_CHANNEL}"
    )
