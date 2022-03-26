"""Tests for dlna_dms.media_source, mostly testing DmsMediaSource."""
from unittest.mock import ANY, Mock

from async_upnp_client.exceptions import UpnpError
from didl_lite import didl_lite
import pytest

from homeassistant.components.dlna_dms.const import DOMAIN
from homeassistant.components.dlna_dms.dms import DlnaDmsData, DmsDeviceSource
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
    MOCK_DEVICE_USN,
    MOCK_SOURCE_ID,
)

from tests.common import MockConfigEntry


@pytest.fixture
async def entity(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    dms_device_mock: Mock,
    domain_data_mock: DlnaDmsData,
) -> DmsDeviceSource:
    """Fixture to set up a DmsDeviceSource in a connected state and cleanup at completion."""
    await hass.config_entries.async_add(config_entry_mock)
    await hass.async_block_till_done()
    return domain_data_mock.devices[MOCK_DEVICE_USN]


@pytest.fixture
async def dms_source(hass: HomeAssistant, entity: DmsDeviceSource) -> DmsMediaSource:
    """Fixture providing a pre-constructed DmsMediaSource with a single device."""
    return DmsMediaSource(hass)


async def test_get_media_source(hass: HomeAssistant) -> None:
    """Test the async_get_media_source function and DmsMediaSource constructor."""
    source = await async_get_media_source(hass)
    assert isinstance(source, DmsMediaSource)
    assert source.domain == DOMAIN


async def test_resolve_media_unconfigured(hass: HomeAssistant) -> None:
    """Test resolve_media without any devices being configured."""
    source = DmsMediaSource(hass)
    item = MediaSourceItem(hass, DOMAIN, "source_id/media_id")
    with pytest.raises(Unresolvable, match="No sources have been configured"):
        await source.async_resolve_media(item)


async def test_resolve_media_bad_identifier(
    hass: HomeAssistant, dms_source: DmsMediaSource
) -> None:
    """Test trying to resolve an item that has an unresolvable identifier."""
    # Empty identifier
    item = MediaSourceItem(hass, DOMAIN, "")
    with pytest.raises(Unresolvable, match="No source ID.*"):
        await dms_source.async_resolve_media(item)

    # Identifier has media_id but no source_id
    item = MediaSourceItem(hass, DOMAIN, "/media_id")
    with pytest.raises(Unresolvable, match="No source ID.*"):
        await dms_source.async_resolve_media(item)

    # Identifier has source_id but no media_id
    item = MediaSourceItem(hass, DOMAIN, "source_id/")
    with pytest.raises(Unresolvable, match="No media ID.*"):
        await dms_source.async_resolve_media(item)

    # Identifier is missing source_id/media_id separator
    item = MediaSourceItem(hass, DOMAIN, "source_id")
    with pytest.raises(Unresolvable, match="No media ID.*"):
        await dms_source.async_resolve_media(item)

    # Identifier has an unknown source_id
    item = MediaSourceItem(hass, DOMAIN, "unknown_source/media_id")
    with pytest.raises(Unresolvable, match="Unknown source ID: unknown_source"):
        await dms_source.async_resolve_media(item)


async def test_resolve_media_success(
    hass: HomeAssistant, dms_source: DmsMediaSource, dms_device_mock: Mock
) -> None:
    """Test resolving an item via a DmsDeviceSource."""
    object_id = "123"
    item = MediaSourceItem(hass, DOMAIN, f"{MOCK_SOURCE_ID}/:{object_id}")

    res_url = "foo/bar"
    res_mime = "audio/mpeg"
    didl_item = didl_lite.Item(
        id=object_id,
        restricted=False,
        title="Object",
        res=[didl_lite.Resource(uri=res_url, protocol_info=f"http-get:*:{res_mime}:")],
    )
    dms_device_mock.async_browse_metadata.return_value = didl_item

    result = await dms_source.async_resolve_media(item)
    assert result.url == f"{MOCK_DEVICE_BASE_URL}/{res_url}"
    assert result.mime_type == res_mime
    assert result.didl_metadata is didl_item


async def test_browse_media_unconfigured(hass: HomeAssistant) -> None:
    """Test browse_media without any devices being configured."""
    source = DmsMediaSource(hass)
    item = MediaSourceItem(hass, DOMAIN, "source_id/media_id")
    with pytest.raises(BrowseError, match="No sources have been configured"):
        await source.async_browse_media(item)

    item = MediaSourceItem(hass, DOMAIN, "")
    with pytest.raises(BrowseError, match="No sources have been configured"):
        await source.async_browse_media(item)


async def test_browse_media_bad_identifier(
    hass: HomeAssistant, dms_source: DmsMediaSource
) -> None:
    """Test browse_media with a bad source_id."""
    item = MediaSourceItem(hass, DOMAIN, "bad-id/media_id")
    with pytest.raises(BrowseError, match="Unknown source ID: bad-id"):
        await dms_source.async_browse_media(item)


async def test_browse_media_single_source_no_identifier(
    hass: HomeAssistant, dms_source: DmsMediaSource, dms_device_mock: Mock
) -> None:
    """Test browse_media without a source_id, with a single device registered."""
    # Fast bail-out, mock will be checked after
    dms_device_mock.async_browse_metadata.side_effect = UpnpError

    # No source_id nor media_id
    item = MediaSourceItem(hass, DOMAIN, "")
    with pytest.raises(BrowseError):
        await dms_source.async_browse_media(item)
    # Mock device should've been browsed for the root directory
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        "0", metadata_filter=ANY
    )

    # No source_id but a media_id
    item = MediaSourceItem(hass, DOMAIN, "/:media-item-id")
    dms_device_mock.async_browse_metadata.reset_mock()
    with pytest.raises(BrowseError):
        await dms_source.async_browse_media(item)
    # Mock device should've been browsed for the root directory
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        "media-item-id", metadata_filter=ANY
    )


async def test_browse_media_multiple_sources(
    hass: HomeAssistant, dms_source: DmsMediaSource, dms_device_mock: Mock
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
    await hass.config_entries.async_add(other_config_entry)
    await hass.async_block_till_done()

    # No source_id nor media_id
    item = MediaSourceItem(hass, DOMAIN, "")
    result = await dms_source.async_browse_media(item)
    # Mock device should not have been browsed
    assert dms_device_mock.async_browse_metadata.await_count == 0
    # Result will be a list of available devices
    assert result.title == "DLNA Servers"
    assert result.children
    assert isinstance(result.children[0], BrowseMediaSource)
    assert result.children[0].identifier == f"{MOCK_SOURCE_ID}/:0"
    assert result.children[0].title == MOCK_DEVICE_NAME
    assert isinstance(result.children[1], BrowseMediaSource)
    assert result.children[1].identifier == f"{other_source_id}/:0"
    assert result.children[1].title == other_source_title

    # No source_id but a media_id - will give the exact same list of all devices
    item = MediaSourceItem(hass, DOMAIN, "/:media-item-id")
    result = await dms_source.async_browse_media(item)
    # Mock device should not have been browsed
    assert dms_device_mock.async_browse_metadata.await_count == 0
    # Result will be a list of available devices
    assert result.title == "DLNA Servers"
    assert result.children
    assert isinstance(result.children[0], BrowseMediaSource)
    assert result.children[0].identifier == f"{MOCK_SOURCE_ID}/:0"
    assert result.children[0].title == MOCK_DEVICE_NAME
    assert isinstance(result.children[1], BrowseMediaSource)
    assert result.children[1].identifier == f"{other_source_id}/:0"
    assert result.children[1].title == other_source_title


async def test_browse_media_source_id(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    dms_device_mock: Mock,
    domain_data_mock: DlnaDmsData,
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
    await hass.config_entries.async_add(other_config_entry)
    await hass.async_block_till_done()

    await hass.config_entries.async_add(config_entry_mock)
    await hass.async_block_till_done()

    # Fast bail-out, mock will be checked after
    dms_device_mock.async_browse_metadata.side_effect = UpnpError

    # Browse by source_id
    item = MediaSourceItem(hass, DOMAIN, f"{MOCK_SOURCE_ID}/:media-item-id")
    dms_source = DmsMediaSource(hass)
    with pytest.raises(BrowseError):
        await dms_source.async_browse_media(item)
    # Mock device should've been browsed for the root directory
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        "media-item-id", metadata_filter=ANY
    )
