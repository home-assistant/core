"""Tests for dlna_dms.media_source, mostly testing DmsMediaSource."""

from unittest.mock import ANY, Mock

from async_upnp_client.exceptions import UpnpError
from didl_lite import didl_lite
import pytest

from homeassistant.components import media_source
from homeassistant.components.dlna_dms.const import DOMAIN
from homeassistant.components.dlna_dms.dms import DidlPlayMedia
from homeassistant.components.dlna_dms.media_source import (
    DmsMediaSource,
    async_get_media_source,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSourceItem,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_URL
from homeassistant.core import HomeAssistant

from .conftest import (
    MOCK_DEVICE_BASE_URL,
    MOCK_DEVICE_NAME,
    MOCK_DEVICE_TYPE,
    MOCK_SOURCE_ID,
)

from tests.common import MockConfigEntry

# Auto-use a few fixtures from conftest
pytestmark = [
    # Block network access
    pytest.mark.usefixtures("aiohttp_session_requester_mock"),
    # Setup the media_source platform
    pytest.mark.usefixtures("setup_media_source"),
]


async def test_get_media_source(hass: HomeAssistant) -> None:
    """Test the async_get_media_source function and DmsMediaSource constructor."""
    source = await async_get_media_source(hass)
    assert isinstance(source, DmsMediaSource)
    assert source.domain == DOMAIN


async def test_resolve_media_unconfigured(hass: HomeAssistant) -> None:
    """Test resolve_media without any devices being configured."""
    source = DmsMediaSource(hass)
    item = MediaSourceItem(hass, DOMAIN, "source_id/media_id", None)
    with pytest.raises(Unresolvable, match="No sources have been configured"):
        await source.async_resolve_media(item)


async def test_resolve_media_bad_identifier(
    hass: HomeAssistant, device_source_mock: None
) -> None:
    """Test trying to resolve an item that has an unresolvable identifier."""
    # Empty identifier
    with pytest.raises(Unresolvable, match="No source ID.*"):
        await media_source.async_resolve_media(hass, f"media-source://{DOMAIN}", None)

    # Identifier has media_id but no source_id
    # media_source.URI_SCHEME_REGEX won't let the ID through to dlna_dms
    with pytest.raises(Unresolvable, match="Invalid media source URI"):
        await media_source.async_resolve_media(
            hass, f"media-source://{DOMAIN}//media_id", None
        )

    # Identifier has source_id but no media_id
    with pytest.raises(Unresolvable, match="No media ID.*"):
        await media_source.async_resolve_media(
            hass, f"media-source://{DOMAIN}/source_id/", None
        )

    # Identifier is missing source_id/media_id separator
    with pytest.raises(Unresolvable, match="No media ID.*"):
        await media_source.async_resolve_media(
            hass, f"media-source://{DOMAIN}/source_id", None
        )

    # Identifier has an unknown source_id
    with pytest.raises(Unresolvable, match="Unknown source ID: unknown_source"):
        await media_source.async_resolve_media(
            hass, f"media-source://{DOMAIN}/unknown_source/media_id", None
        )


async def test_resolve_media_success(
    hass: HomeAssistant, dms_device_mock: Mock, device_source_mock: None
) -> None:
    """Test resolving an item via a DmsDeviceSource."""
    object_id = "123"

    res_url = "foo/bar"
    res_mime = "audio/mpeg"
    didl_item = didl_lite.Item(
        id=object_id,
        restricted=False,
        title="Object",
        res=[didl_lite.Resource(uri=res_url, protocol_info=f"http-get:*:{res_mime}:")],
    )
    dms_device_mock.async_browse_metadata.return_value = didl_item

    result = await media_source.async_resolve_media(
        hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/:{object_id}", None
    )
    assert isinstance(result, DidlPlayMedia)
    assert result.url == f"{MOCK_DEVICE_BASE_URL}/{res_url}"
    assert result.mime_type == res_mime
    assert result.didl_metadata is didl_item


async def test_browse_media_unconfigured(hass: HomeAssistant) -> None:
    """Test browse_media without any devices being configured."""
    source = DmsMediaSource(hass)
    item = MediaSourceItem(hass, DOMAIN, "source_id/media_id", None)
    with pytest.raises(BrowseError, match="No sources have been configured"):
        await source.async_browse_media(item)

    item = MediaSourceItem(hass, DOMAIN, "", None)
    with pytest.raises(BrowseError, match="No sources have been configured"):
        await source.async_browse_media(item)


async def test_browse_media_bad_identifier(
    hass: HomeAssistant, device_source_mock: None
) -> None:
    """Test browse_media with a bad source_id."""
    with pytest.raises(BrowseError, match="Unknown source ID: bad-id"):
        await media_source.async_browse_media(
            hass, f"media-source://{DOMAIN}/bad-id/media_id"
        )


async def test_browse_media_single_source_no_identifier(
    hass: HomeAssistant, dms_device_mock: Mock, device_source_mock: None
) -> None:
    """Test browse_media without a source_id, with a single device registered."""
    # Fast bail-out, mock will be checked after
    dms_device_mock.async_browse_metadata.side_effect = UpnpError

    # No source_id nor media_id
    with pytest.raises(BrowseError):
        await media_source.async_browse_media(hass, f"media-source://{DOMAIN}")
    # Mock device should've been browsed for the root directory
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        "0", metadata_filter=ANY
    )

    # No source_id but a media_id
    # media_source.URI_SCHEME_REGEX won't let the ID through to dlna_dms
    dms_device_mock.async_browse_metadata.reset_mock()
    with pytest.raises(BrowseError, match="Invalid media source URI"):
        await media_source.async_browse_media(
            hass, f"media-source://{DOMAIN}//:media-item-id"
        )
    assert dms_device_mock.async_browse_metadata.await_count == 0


async def test_browse_media_multiple_sources(
    hass: HomeAssistant, dms_device_mock: Mock, device_source_mock: None
) -> None:
    """Test browse_media without a source_id, with multiple devices registered."""
    # Set up a second source
    other_source_id = "second_source"
    other_source_title = "Second source"
    other_config_entry = MockConfigEntry(
        unique_id=f"different-udn::{MOCK_DEVICE_TYPE}",
        domain=DOMAIN,
        data={
            CONF_URL: "http://192.88.99.22/dms_description.xml",
            CONF_DEVICE_ID: f"different-udn::{MOCK_DEVICE_TYPE}",
        },
        title=other_source_title,
    )
    other_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(other_config_entry.entry_id)
    await hass.async_block_till_done()

    # No source_id nor media_id
    result = await media_source.async_browse_media(hass, f"media-source://{DOMAIN}")
    # Mock device should not have been browsed
    assert dms_device_mock.async_browse_metadata.await_count == 0
    # Result will be a list of available devices
    assert result.title == "DLNA Servers"
    assert result.children
    assert isinstance(result.children[0], BrowseMediaSource)
    assert result.children[0].identifier == f"{MOCK_SOURCE_ID}/:0"
    assert result.children[0].title == MOCK_DEVICE_NAME
    assert result.children[0].thumbnail == dms_device_mock.icon
    assert isinstance(result.children[1], BrowseMediaSource)
    assert result.children[1].identifier == f"{other_source_id}/:0"
    assert result.children[1].title == other_source_title

    # No source_id but a media_id
    # media_source.URI_SCHEME_REGEX won't let the ID through to dlna_dms
    with pytest.raises(BrowseError, match="Invalid media source URI"):
        result = await media_source.async_browse_media(
            hass, f"media-source://{DOMAIN}//:media-item-id"
        )
    # Mock device should not have been browsed
    assert dms_device_mock.async_browse_metadata.await_count == 0

    # Clean up, to fulfil ssdp_scanner post-condition of every callback being cleared
    await hass.config_entries.async_remove(other_config_entry.entry_id)


async def test_browse_media_source_id(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    dms_device_mock: Mock,
) -> None:
    """Test browse_media with an explicit source_id."""
    # Set up a second device first, then the primary mock device.
    # This allows testing that the right source is chosen by source_id
    other_source_title = "Second source"
    other_config_entry = MockConfigEntry(
        unique_id=f"different-udn::{MOCK_DEVICE_TYPE}",
        domain=DOMAIN,
        data={
            CONF_URL: "http://192.88.99.22/dms_description.xml",
            CONF_DEVICE_ID: f"different-udn::{MOCK_DEVICE_TYPE}",
        },
        title=other_source_title,
    )

    other_config_entry.add_to_hass(hass)
    config_entry_mock.add_to_hass(hass)

    # Setting up either config entry will result in the dlna_dms component being
    # loaded, and both config entries will be setup
    await hass.config_entries.async_setup(other_config_entry.entry_id)
    await hass.async_block_till_done()

    # Fast bail-out, mock will be checked after
    dms_device_mock.async_browse_metadata.side_effect = UpnpError

    # Browse by source_id
    item = MediaSourceItem(hass, DOMAIN, f"{MOCK_SOURCE_ID}/:media-item-id", None)
    dms_source = DmsMediaSource(hass)
    with pytest.raises(BrowseError):
        await dms_source.async_browse_media(item)
    # Mock device should've been browsed for the root directory
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        "media-item-id", metadata_filter=ANY
    )
