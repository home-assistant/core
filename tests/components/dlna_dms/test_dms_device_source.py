"""Test the interface methods of DmsDeviceSource, except availability."""
from collections.abc import AsyncIterable
from typing import Final, Union
from unittest.mock import ANY, Mock, call

from async_upnp_client.exceptions import UpnpActionError, UpnpConnectionError, UpnpError
from async_upnp_client.profiles.dlna import ContentDirectoryErrorCode, DmsDevice
from didl_lite import didl_lite
import pytest

from homeassistant.components.dlna_dms.const import DOMAIN
from homeassistant.components.dlna_dms.dms import (
    ActionError,
    DeviceConnectionError,
    DlnaDmsData,
    DmsDeviceSource,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import BrowseMediaSource
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

BrowseResultList = list[Union[didl_lite.DidlObject, didl_lite.Descriptor]]


@pytest.fixture
async def device_source_mock(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dms_device_mock: Mock,
    domain_data_mock: DlnaDmsData,
) -> AsyncIterable[DmsDeviceSource]:
    """Fixture to set up a DmsDeviceSource in a connected state and cleanup at completion."""
    await hass.config_entries.async_add(config_entry_mock)
    await hass.async_block_till_done()

    mock_entity = domain_data_mock.devices[MOCK_DEVICE_USN]

    # Check the DmsDeviceSource has registered all needed listeners
    assert len(config_entry_mock.update_listeners) == 1
    assert ssdp_scanner_mock.async_register_callback.await_count == 2
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 0

    # Run the test
    yield mock_entity

    # Unload config entry to clean up
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Check DmsDeviceSource has cleaned up its resources
    assert not config_entry_mock.update_listeners
    assert (
        ssdp_scanner_mock.async_register_callback.await_count
        == ssdp_scanner_mock.async_register_callback.return_value.call_count
    )
    assert MOCK_DEVICE_USN not in domain_data_mock.devices
    assert MOCK_SOURCE_ID not in domain_data_mock.sources


async def test_update_source_id(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    device_source_mock: DmsDeviceSource,
    domain_data_mock: DlnaDmsData,
) -> None:
    """Test the config listener updates the source_id and source list upon title change."""
    new_title: Final = "New Name"
    new_source_id: Final = "new_name"
    assert domain_data_mock.sources.keys() == {MOCK_SOURCE_ID}
    hass.config_entries.async_update_entry(config_entry_mock, title=new_title)
    await hass.async_block_till_done()

    assert device_source_mock.source_id == new_source_id
    assert domain_data_mock.sources.keys() == {new_source_id}


async def test_update_existing_source_id(
    caplog: pytest.LogCaptureFixture,
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    device_source_mock: DmsDeviceSource,
    domain_data_mock: DlnaDmsData,
) -> None:
    """Test the config listener gracefully handles colliding source_id."""
    new_title: Final = "New Name"
    new_source_id: Final = "new_name"
    new_source_id_2: Final = "new_name_1"
    # Set up another config entry to collide with the new source_id
    colliding_entry = MockConfigEntry(
        unique_id=f"different-udn::{MOCK_DEVICE_TYPE}",
        domain=DOMAIN,
        data={
            CONF_URL: "http://192.88.99.22/dms_description.xml",
            CONF_DEVICE_ID: f"different-udn::{MOCK_DEVICE_TYPE}",
        },
        title=new_title,
    )
    await hass.config_entries.async_add(colliding_entry)
    await hass.async_block_till_done()

    assert device_source_mock.source_id == MOCK_SOURCE_ID
    assert domain_data_mock.sources.keys() == {MOCK_SOURCE_ID, new_source_id}
    assert domain_data_mock.sources[MOCK_SOURCE_ID] is device_source_mock

    # Update the existing entry to match the other entry's name
    hass.config_entries.async_update_entry(config_entry_mock, title=new_title)
    await hass.async_block_till_done()

    # The existing device's source ID should be a newly generated slug
    assert device_source_mock.source_id == new_source_id_2
    assert domain_data_mock.sources.keys() == {new_source_id, new_source_id_2}
    assert domain_data_mock.sources[new_source_id_2] is device_source_mock

    # Changing back to the old name should not cause issues
    hass.config_entries.async_update_entry(config_entry_mock, title=MOCK_DEVICE_NAME)
    await hass.async_block_till_done()

    assert device_source_mock.source_id == MOCK_SOURCE_ID
    assert domain_data_mock.sources.keys() == {MOCK_SOURCE_ID, new_source_id}
    assert domain_data_mock.sources[MOCK_SOURCE_ID] is device_source_mock

    # Remove the collision and try again
    await hass.config_entries.async_remove(colliding_entry.entry_id)
    assert domain_data_mock.sources.keys() == {MOCK_SOURCE_ID}

    hass.config_entries.async_update_entry(config_entry_mock, title=new_title)
    await hass.async_block_till_done()

    assert device_source_mock.source_id == new_source_id
    assert domain_data_mock.sources.keys() == {new_source_id}


async def test_catch_request_error_unavailable(
    device_source_mock: DmsDeviceSource,
) -> None:
    """Test the device is checked for availability before trying requests."""
    device_source_mock._device = None

    with pytest.raises(DeviceConnectionError):
        await device_source_mock.async_resolve_object("id")
    with pytest.raises(DeviceConnectionError):
        await device_source_mock.async_resolve_path("path")
    with pytest.raises(DeviceConnectionError):
        await device_source_mock.async_resolve_search("query")
    with pytest.raises(DeviceConnectionError):
        await device_source_mock.async_browse_object("object_id")
    with pytest.raises(DeviceConnectionError):
        await device_source_mock.async_browse_search("query")


async def test_catch_request_error(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test errors when making requests to the device are handled."""
    dms_device_mock.async_browse_metadata.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.NO_SUCH_OBJECT
    )
    with pytest.raises(ActionError, match="No such object: bad_id"):
        await device_source_mock.async_resolve_media(":bad_id")

    dms_device_mock.async_search_directory.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.INVALID_SEARCH_CRITERIA
    )
    with pytest.raises(ActionError, match="Invalid query: bad query"):
        await device_source_mock.async_resolve_media("?bad query")

    dms_device_mock.async_browse_metadata.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.CANNOT_PROCESS_REQUEST
    )
    with pytest.raises(DeviceConnectionError, match="Server failure: "):
        await device_source_mock.async_resolve_media(":good_id")

    dms_device_mock.async_browse_metadata.side_effect = UpnpError
    with pytest.raises(
        DeviceConnectionError, match="Server communication failure: UpnpError(.*)"
    ):
        await device_source_mock.async_resolve_media(":bad_id")

    # UpnpConnectionErrors will cause the device_source_mock to disconnect from the device
    assert device_source_mock.available
    dms_device_mock.async_browse_metadata.side_effect = UpnpConnectionError
    with pytest.raises(
        DeviceConnectionError, match="Server disconnected: UpnpConnectionError(.*)"
    ):
        await device_source_mock.async_resolve_media(":bad_id")
    assert not device_source_mock.available


async def test_icon(device_source_mock: DmsDeviceSource, dms_device_mock: Mock) -> None:
    """Test the device's icon URL is returned."""
    assert device_source_mock.icon == dms_device_mock.icon

    device_source_mock._device = None
    assert device_source_mock.icon is None


async def test_resolve_media_invalid(device_source_mock: DmsDeviceSource) -> None:
    """Test async_resolve_media will raise Unresolvable when an identifier isn't supplied."""
    with pytest.raises(Unresolvable, match="Invalid identifier.*"):
        await device_source_mock.async_resolve_media("")


async def test_resolve_media_object(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test the async_resolve_object method via async_resolve_media."""
    object_id: Final = "123"
    res_url: Final = "foo/bar"
    res_abs_url: Final = f"{MOCK_DEVICE_BASE_URL}/{res_url}"
    res_mime: Final = "audio/mpeg"
    # Success case: one resource
    didl_item = didl_lite.Item(
        id=object_id,
        restricted="false",
        title="Object",
        res=[didl_lite.Resource(uri=res_url, protocol_info=f"http-get:*:{res_mime}:")],
    )
    dms_device_mock.async_browse_metadata.return_value = didl_item
    result = await device_source_mock.async_resolve_media(f":{object_id}")
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        object_id, metadata_filter="*"
    )
    assert result.url == res_abs_url
    assert result.mime_type == res_mime
    assert result.didl_metadata is didl_item

    # Success case: two resources, first is playable
    didl_item = didl_lite.Item(
        id=object_id,
        restricted="false",
        title="Object",
        res=[
            didl_lite.Resource(uri=res_url, protocol_info=f"http-get:*:{res_mime}:"),
            didl_lite.Resource(
                uri="thumbnail.png", protocol_info="http-get:*:image/png:"
            ),
        ],
    )
    dms_device_mock.async_browse_metadata.return_value = didl_item
    result = await device_source_mock.async_resolve_media(f":{object_id}")
    assert result.url == res_abs_url
    assert result.mime_type == res_mime
    assert result.didl_metadata is didl_item

    # Success case: three resources, only third is playable
    didl_item = didl_lite.Item(
        id=object_id,
        restricted="false",
        title="Object",
        res=[
            didl_lite.Resource(uri="", protocol_info=""),
            didl_lite.Resource(uri="internal:thing", protocol_info="internal:*::"),
            didl_lite.Resource(uri=res_url, protocol_info=f"http-get:*:{res_mime}:"),
        ],
    )
    dms_device_mock.async_browse_metadata.return_value = didl_item
    result = await device_source_mock.async_resolve_media(f":{object_id}")
    assert result.url == res_abs_url
    assert result.mime_type == res_mime
    assert result.didl_metadata is didl_item

    # Failure case: no resources
    didl_item = didl_lite.Item(
        id=object_id,
        restricted="false",
        title="Object",
        res=[],
    )
    dms_device_mock.async_browse_metadata.return_value = didl_item
    with pytest.raises(Unresolvable, match="Object has no resources"):
        await device_source_mock.async_resolve_media(f":{object_id}")

    # Failure case: resources are not playable
    didl_item = didl_lite.Item(
        id=object_id,
        restricted="false",
        title="Object",
        res=[didl_lite.Resource(uri="internal:thing", protocol_info="internal:*::")],
    )
    dms_device_mock.async_browse_metadata.return_value = didl_item
    with pytest.raises(Unresolvable, match="Object has no playable resources"):
        await device_source_mock.async_resolve_media(f":{object_id}")


async def test_resolve_media_path(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test the async_resolve_path method via async_resolve_media."""
    path: Final = "path/to/thing"
    object_ids: Final = ["path_id", "to_id", "thing_id"]
    res_url: Final = "foo/bar"
    res_abs_url: Final = f"{MOCK_DEVICE_BASE_URL}/{res_url}"
    res_mime: Final = "audio/mpeg"

    search_directory_result = []
    for ob_id, ob_title in zip(object_ids, path.split("/")):
        didl_item = didl_lite.Item(
            id=ob_id,
            restricted="false",
            title=ob_title,
            res=[],
        )
        search_directory_result.append(DmsDevice.BrowseResult([didl_item], 1, 1, 0))

    # Test that path is resolved correctly
    dms_device_mock.async_search_directory.side_effect = search_directory_result
    dms_device_mock.async_browse_metadata.return_value = didl_lite.Item(
        id=object_ids[-1],
        restricted="false",
        title="thing",
        res=[didl_lite.Resource(uri=res_url, protocol_info=f"http-get:*:{res_mime}:")],
    )
    result = await device_source_mock.async_resolve_media(f"/{path}")
    assert dms_device_mock.async_search_directory.await_args_list == [
        call(
            parent_id,
            search_criteria=f'@parentID="{parent_id}" and dc:title="{title}"',
            metadata_filter=["id", "upnp:class", "dc:title"],
            requested_count=1,
        )
        for parent_id, title in zip(["0"] + object_ids[:-1], path.split("/"))
    ]
    assert result.url == res_abs_url
    assert result.mime_type == res_mime

    # Test a path starting with a / (first / is path action, second / is root of path)
    dms_device_mock.async_search_directory.reset_mock()
    dms_device_mock.async_search_directory.side_effect = search_directory_result
    result = await device_source_mock.async_resolve_media(f"//{path}")
    assert dms_device_mock.async_search_directory.await_args_list == [
        call(
            parent_id,
            search_criteria=f'@parentID="{parent_id}" and dc:title="{title}"',
            metadata_filter=["id", "upnp:class", "dc:title"],
            requested_count=1,
        )
        for parent_id, title in zip(["0"] + object_ids[:-1], path.split("/"))
    ]
    assert result.url == res_abs_url
    assert result.mime_type == res_mime


async def test_resolve_path_simple(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_resolve_path for simple success as for test_resolve_media_path."""
    path: Final = "path/to/thing"
    object_ids: Final = ["path_id", "to_id", "thing_id"]
    search_directory_result = []
    for ob_id, ob_title in zip(object_ids, path.split("/")):
        didl_item = didl_lite.Item(
            id=ob_id,
            restricted="false",
            title=ob_title,
            res=[],
        )
        search_directory_result.append(DmsDevice.BrowseResult([didl_item], 1, 1, 0))

    dms_device_mock.async_search_directory.side_effect = search_directory_result
    result = await device_source_mock.async_resolve_path(path)
    assert dms_device_mock.async_search_directory.call_args_list == [
        call(
            parent_id,
            search_criteria=f'@parentID="{parent_id}" and dc:title="{title}"',
            metadata_filter=["id", "upnp:class", "dc:title"],
            requested_count=1,
        )
        for parent_id, title in zip(["0"] + object_ids[:-1], path.split("/"))
    ]
    assert result == object_ids[-1]
    assert not dms_device_mock.async_browse_direct_children.await_count


async def test_resolve_path_browsed(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_resolve_path: action error results in browsing."""
    path: Final = "path/to/thing"
    object_ids: Final = ["path_id", "to_id", "thing_id"]

    search_directory_result = []
    for ob_id, ob_title in zip(object_ids, path.split("/")):
        didl_item = didl_lite.Item(
            id=ob_id,
            restricted="false",
            title=ob_title,
            res=[],
        )
        search_directory_result.append(DmsDevice.BrowseResult([didl_item], 1, 1, 0))
    dms_device_mock.async_search_directory.side_effect = [
        search_directory_result[0],
        # 2nd level can't be searched (this happens with Kodi)
        UpnpActionError(),
        search_directory_result[2],
    ]

    browse_children_result: BrowseResultList = []
    for title in ("Irrelevant", "to", "Ignored"):
        browse_children_result.append(
            didl_lite.Item(id=f"{title}_id", restricted="false", title=title, res=[])
        )
    dms_device_mock.async_browse_direct_children.side_effect = [
        DmsDevice.BrowseResult(browse_children_result, 3, 3, 0)
    ]

    result = await device_source_mock.async_resolve_path(path)
    # All levels should have an attempted search
    assert dms_device_mock.async_search_directory.await_args_list == [
        call(
            parent_id,
            search_criteria=f'@parentID="{parent_id}" and dc:title="{title}"',
            metadata_filter=["id", "upnp:class", "dc:title"],
            requested_count=1,
        )
        for parent_id, title in zip(["0"] + object_ids[:-1], path.split("/"))
    ]
    assert result == object_ids[-1]
    # 2nd level should also be browsed
    assert dms_device_mock.async_browse_direct_children.await_args_list == [
        call("path_id", metadata_filter=["id", "upnp:class", "dc:title"])
    ]


async def test_resolve_path_browsed_nothing(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_resolve_path: action error results in browsing, but nothing found."""
    dms_device_mock.async_search_directory.side_effect = UpnpActionError()
    # No children
    dms_device_mock.async_browse_direct_children.side_effect = [
        DmsDevice.BrowseResult([], 0, 0, 0)
    ]
    with pytest.raises(Unresolvable, match="No contents for thing in thing/other"):
        await device_source_mock.async_resolve_path(r"thing/other")

    # There are children, but they don't match
    dms_device_mock.async_browse_direct_children.side_effect = [
        DmsDevice.BrowseResult(
            [
                didl_lite.Item(
                    id="nothingid", restricted="false", title="not thing", res=[]
                )
            ],
            1,
            1,
            0,
        )
    ]
    with pytest.raises(Unresolvable, match="Nothing found for thing in thing/other"):
        await device_source_mock.async_resolve_path(r"thing/other")


async def test_resolve_path_quoted(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_resolve_path: quotes and backslashes in the path get escaped correctly."""
    dms_device_mock.async_search_directory.side_effect = [
        DmsDevice.BrowseResult(
            [
                didl_lite.Item(
                    id=r'id_with quote" and back\slash',
                    restricted="false",
                    title="path",
                    res=[],
                )
            ],
            1,
            1,
            0,
        ),
        UpnpError("Quick abort"),
    ]
    with pytest.raises(DeviceConnectionError):
        await device_source_mock.async_resolve_path(r'path/quote"back\slash')
    assert dms_device_mock.async_search_directory.await_args_list == [
        call(
            "0",
            search_criteria='@parentID="0" and dc:title="path"',
            metadata_filter=["id", "upnp:class", "dc:title"],
            requested_count=1,
        ),
        call(
            r'id_with quote" and back\slash',
            search_criteria=r'@parentID="id_with quote\" and back\\slash" and dc:title="quote\"back\\slash"',
            metadata_filter=["id", "upnp:class", "dc:title"],
            requested_count=1,
        ),
    ]


async def test_resolve_path_ambiguous(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_resolve_path: ambiguous results (too many matches) gives error."""
    dms_device_mock.async_search_directory.side_effect = [
        DmsDevice.BrowseResult(
            [
                didl_lite.Item(
                    id=r"thing 1",
                    restricted="false",
                    title="thing",
                    res=[],
                ),
                didl_lite.Item(
                    id=r"thing 2",
                    restricted="false",
                    title="thing",
                    res=[],
                ),
            ],
            2,
            2,
            0,
        )
    ]
    with pytest.raises(
        Unresolvable, match="Too many items found for thing in thing/other"
    ):
        await device_source_mock.async_resolve_path(r"thing/other")


async def test_resolve_path_no_such_container(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_resolve_path: Explicit check for NO_SUCH_CONTAINER."""
    dms_device_mock.async_search_directory.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.NO_SUCH_CONTAINER
    )
    with pytest.raises(Unresolvable, match="No such container: 0"):
        await device_source_mock.async_resolve_path(r"thing/other")


async def test_resolve_media_search(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test the async_resolve_search method via async_resolve_media."""
    res_url: Final = "foo/bar"
    res_abs_url: Final = f"{MOCK_DEVICE_BASE_URL}/{res_url}"
    res_mime: Final = "audio/mpeg"

    # No results
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )
    with pytest.raises(Unresolvable, match='Nothing found for dc:title="thing"'):
        await device_source_mock.async_resolve_media('?dc:title="thing"')
    assert dms_device_mock.async_search_directory.await_args_list == [
        call(
            container_id="0",
            search_criteria='dc:title="thing"',
            metadata_filter="*",
            requested_count=1,
        )
    ]

    # One result
    dms_device_mock.async_search_directory.reset_mock()
    didl_item = didl_lite.Item(
        id="thing's id",
        restricted="false",
        title="thing",
        res=[didl_lite.Resource(uri=res_url, protocol_info=f"http-get:*:{res_mime}:")],
    )
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [didl_item], 1, 1, 0
    )
    result = await device_source_mock.async_resolve_media('?dc:title="thing"')
    assert result.url == res_abs_url
    assert result.mime_type == res_mime
    assert result.didl_metadata is didl_item
    assert dms_device_mock.async_search_directory.await_count == 1
    # Values should be taken from search result, not querying the item's metadata
    assert dms_device_mock.async_browse_metadata.await_count == 0

    # Two results - uses the first
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [didl_item], 1, 2, 0
    )
    result = await device_source_mock.async_resolve_media('?dc:title="thing"')
    assert result.url == res_abs_url
    assert result.mime_type == res_mime
    assert result.didl_metadata is didl_item

    # Bad result
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [didl_lite.Descriptor("id", "namespace")], 1, 1, 0
    )
    with pytest.raises(Unresolvable, match="Descriptor.* is not a DidlObject"):
        await device_source_mock.async_resolve_media('?dc:title="thing"')


async def test_browse_media_root(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_browse_media with no identifier will browse the root of the device."""
    dms_device_mock.async_browse_metadata.return_value = didl_lite.DidlObject(
        id="0", restricted="false", title="root"
    )
    dms_device_mock.async_browse_direct_children.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )
    # No identifier (first opened in media browser)
    result = await device_source_mock.async_browse_media(None)
    assert result.identifier == f"{MOCK_SOURCE_ID}/:0"
    assert result.title == MOCK_DEVICE_NAME
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        "0", metadata_filter=ANY
    )
    dms_device_mock.async_browse_direct_children.assert_awaited_once_with(
        "0", metadata_filter=ANY, sort_criteria=ANY
    )

    dms_device_mock.async_browse_metadata.reset_mock()
    dms_device_mock.async_browse_direct_children.reset_mock()
    # Empty string identifier
    result = await device_source_mock.async_browse_media("")
    assert result.identifier == f"{MOCK_SOURCE_ID}/:0"
    assert result.title == MOCK_DEVICE_NAME
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        "0", metadata_filter=ANY
    )
    dms_device_mock.async_browse_direct_children.assert_awaited_once_with(
        "0", metadata_filter=ANY, sort_criteria=ANY
    )


async def test_browse_media_object(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_browse_object via async_browse_media."""
    object_id = "1234"
    child_titles = ("Item 1", "Thing", "Item 2")
    dms_device_mock.async_browse_metadata.return_value = didl_lite.Container(
        id=object_id, restricted="false", title="subcontainer"
    )
    children_result = DmsDevice.BrowseResult([], 3, 3, 0)
    for title in child_titles:
        children_result.result.append(
            didl_lite.Item(
                id=title + "_id",
                restricted="false",
                title=title,
                res=[
                    didl_lite.Resource(
                        uri=title + "_url", protocol_info="http-get:*:audio/mpeg:"
                    )
                ],
            ),
        )
    dms_device_mock.async_browse_direct_children.return_value = children_result

    result = await device_source_mock.async_browse_media(f":{object_id}")
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        object_id, metadata_filter=ANY
    )
    dms_device_mock.async_browse_direct_children.assert_awaited_once_with(
        object_id, metadata_filter=ANY, sort_criteria=ANY
    )

    assert result.domain == DOMAIN
    assert result.identifier == f"{MOCK_SOURCE_ID}/:{object_id}"
    assert result.title == "subcontainer"
    assert not result.can_play
    assert result.can_expand
    assert result.children
    for child, title in zip(result.children, child_titles):
        assert isinstance(child, BrowseMediaSource)
        assert child.identifier == f"{MOCK_SOURCE_ID}/:{title}_id"
        assert child.title == title
        assert child.can_play
        assert not child.can_expand
        assert not child.children


async def test_browse_media_path(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_browse_media with a path."""
    title = "folder"
    con_id = "123"
    container = didl_lite.Container(id=con_id, restricted="false", title=title)
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [container], 1, 1, 0
    )
    dms_device_mock.async_browse_metadata.return_value = container
    dms_device_mock.async_browse_direct_children.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )

    result = await device_source_mock.async_browse_media(f"{title}")
    assert result.identifier == f"{MOCK_SOURCE_ID}/:{con_id}"
    assert result.title == title

    dms_device_mock.async_search_directory.assert_awaited_once_with(
        "0",
        search_criteria=f'@parentID="0" and dc:title="{title}"',
        metadata_filter=ANY,
        requested_count=1,
    )
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        con_id, metadata_filter=ANY
    )
    dms_device_mock.async_browse_direct_children.assert_awaited_once_with(
        con_id, metadata_filter=ANY, sort_criteria=ANY
    )


async def test_browse_media_search(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test async_browse_media with a search query."""
    query = 'dc:title contains "FooBar"'
    object_details = (("111", "FooBar baz"), ("432", "Not FooBar"), ("99", "FooBar"))
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [
            didl_lite.DidlObject(id=ob_id, restricted="false", title=title)
            for ob_id, title in object_details
        ],
        3,
        3,
        0,
    )
    # Test that descriptors are skipped
    dms_device_mock.async_search_directory.return_value.result.insert(
        1, didl_lite.Descriptor("id", "name_space")
    )

    result = await device_source_mock.async_browse_media(f"?{query}")
    assert result.identifier == f"{MOCK_SOURCE_ID}/?{query}"
    assert result.title == "Search results"
    assert result.children

    for obj, child in zip(object_details, result.children):
        assert isinstance(child, BrowseMediaSource)
        assert child.identifier == f"{MOCK_SOURCE_ID}/:{obj[0]}"
        assert child.title == obj[1]
        assert not child.children


async def test_browse_search_invalid(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test searching with an invalid query gives a BrowseError."""
    query = "title == FooBar"
    dms_device_mock.async_search_directory.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.INVALID_SEARCH_CRITERIA
    )
    with pytest.raises(BrowseError, match=f"Invalid query: {query}"):
        await device_source_mock.async_browse_media(f"?{query}")


async def test_browse_search_no_results(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test a search with no results does not give an error."""
    query = 'dc:title contains "FooBar"'
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )

    result = await device_source_mock.async_browse_media(f"?{query}")
    assert result.identifier == f"{MOCK_SOURCE_ID}/?{query}"
    assert result.title == "Search results"
    assert not result.children


async def test_thumbnail(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test getting thumbnails URLs for items."""
    # Use browse_search to get multiple items at once for least effort
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [
            # Thumbnail as albumArtURI property
            didl_lite.MusicAlbum(
                id="a",
                restricted="false",
                title="a",
                res=[],
                album_art_uri="a_thumb.jpg",
            ),
            # Thumbnail as resource (1st resource is media item, 2nd is missing
            # a URI, 3rd is thumbnail)
            didl_lite.MusicTrack(
                id="b",
                restricted="false",
                title="b",
                res=[
                    didl_lite.Resource(
                        uri="b_track.mp3", protocol_info="http-get:*:audio/mpeg:"
                    ),
                    didl_lite.Resource(uri="", protocol_info="internal:*::"),
                    didl_lite.Resource(
                        uri="b_thumb.png", protocol_info="http-get:*:image/png:"
                    ),
                ],
            ),
            # No thumbnail
            didl_lite.MusicTrack(
                id="c",
                restricted="false",
                title="c",
                res=[
                    didl_lite.Resource(
                        uri="c_track.mp3", protocol_info="http-get:*:audio/mpeg:"
                    )
                ],
            ),
        ],
        3,
        3,
        0,
    )

    result = await device_source_mock.async_browse_media("?query")
    assert result.children
    assert result.children[0].thumbnail == f"{MOCK_DEVICE_BASE_URL}/a_thumb.jpg"
    assert result.children[1].thumbnail == f"{MOCK_DEVICE_BASE_URL}/b_thumb.png"
    assert result.children[2].thumbnail is None


async def test_can_play(
    device_source_mock: DmsDeviceSource, dms_device_mock: Mock
) -> None:
    """Test determination of playability for items."""
    protocol_infos = [
        # No protocol info for resource
        ("", True),
        # Protocol info is poorly formatted but can play
        ("http-get", True),
        # Protocol info is poorly formatted and can't play
        ("internal", False),
        # Protocol is HTTP
        ("http-get:*:audio/mpeg", True),
        # Protocol is RTSP
        ("rtsp-rtp-udp:*:MPA:", True),
        # Protocol is something else
        ("internal:*:audio/mpeg:", False),
    ]

    search_results: BrowseResultList = []
    # No resources
    search_results.append(didl_lite.DidlObject(id="", restricted="false", title=""))
    search_results.extend(
        didl_lite.MusicTrack(
            id="",
            restricted="false",
            title="",
            res=[didl_lite.Resource(uri="", protocol_info=protocol_info)],
        )
        for protocol_info, _ in protocol_infos
    )

    # Use browse_search to get multiple items at once for least effort
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        search_results, len(search_results), len(search_results), 0
    )

    result = await device_source_mock.async_browse_media("?query")
    assert result.children
    assert not result.children[0].can_play
    for idx, info_can_play in enumerate(protocol_infos):
        protocol_info, can_play = info_can_play
        assert result.children[idx + 1].can_play is can_play, f"Checked {protocol_info}"
