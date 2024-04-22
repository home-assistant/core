"""Test the browse and resolve methods of DmsDeviceSource."""

from __future__ import annotations

from typing import Final
from unittest.mock import ANY, Mock, call

from async_upnp_client.exceptions import UpnpActionError, UpnpConnectionError, UpnpError
from async_upnp_client.profiles.dlna import ContentDirectoryErrorCode, DmsDevice
from didl_lite import didl_lite
import pytest

from homeassistant.components import media_source, ssdp
from homeassistant.components.dlna_dms.const import DLNA_SORT_CRITERIA, DOMAIN
from homeassistant.components.dlna_dms.dms import DidlPlayMedia
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import BrowseMediaSource
from homeassistant.core import HomeAssistant

from .conftest import (
    MOCK_DEVICE_BASE_URL,
    MOCK_DEVICE_NAME,
    MOCK_DEVICE_TYPE,
    MOCK_DEVICE_UDN,
    MOCK_DEVICE_USN,
    MOCK_SOURCE_ID,
)

# Auto-use a few fixtures from conftest
pytestmark = [
    # Block network access
    pytest.mark.usefixtures("aiohttp_session_requester_mock"),
    # Setup the media_source platform
    pytest.mark.usefixtures("setup_media_source"),
    # Have a connected device so that test can successfully call browse and resolve
    pytest.mark.usefixtures("device_source_mock"),
]


BrowseResultList = list[didl_lite.DidlObject | didl_lite.Descriptor]


async def async_resolve_media(
    hass: HomeAssistant, media_content_id: str
) -> DidlPlayMedia:
    """Call media_source.async_resolve_media with the test source's ID."""
    result = await media_source.async_resolve_media(
        hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/{media_content_id}", None
    )
    assert isinstance(result, DidlPlayMedia)
    return result


async def async_browse_media(
    hass: HomeAssistant,
    media_content_id: str | None,
) -> BrowseMediaSource:
    """Call media_source.async_browse_media with the test source's ID."""
    return await media_source.async_browse_media(
        hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/{media_content_id}"
    )


async def test_catch_request_error_unavailable(
    hass: HomeAssistant, ssdp_scanner_mock: Mock
) -> None:
    """Test the device is checked for availability before trying requests."""
    # DmsDevice notifies of disconnect via SSDP
    ssdp_callback = ssdp_scanner_mock.async_register_callback.call_args.args[0].target
    await ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn=MOCK_DEVICE_USN,
            ssdp_udn=MOCK_DEVICE_UDN,
            ssdp_headers={"NTS": "ssdp:byebye"},
            ssdp_st=MOCK_DEVICE_TYPE,
            upnp={},
        ),
        ssdp.SsdpChange.BYEBYE,
    )

    # All attempts to use the device should give an error
    with pytest.raises(Unresolvable, match="DMS is not connected"):
        # Resolve object
        await async_resolve_media(hass, ":id")
    with pytest.raises(Unresolvable, match="DMS is not connected"):
        # Resolve path
        await async_resolve_media(hass, "/path")
    with pytest.raises(Unresolvable, match="DMS is not connected"):
        # Resolve search
        await async_resolve_media(hass, "?query")
    with pytest.raises(BrowseError, match="DMS is not connected"):
        # Browse object
        await async_browse_media(hass, ":id")
    with pytest.raises(BrowseError, match="DMS is not connected"):
        # Browse path
        await async_browse_media(hass, "/path")
    with pytest.raises(BrowseError, match="DMS is not connected"):
        # Browse search
        await async_browse_media(hass, "?query")


async def test_catch_request_error(hass: HomeAssistant, dms_device_mock: Mock) -> None:
    """Test errors when making requests to the device are handled."""
    dms_device_mock.async_browse_metadata.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.NO_SUCH_OBJECT
    )
    with pytest.raises(Unresolvable, match="No such object: bad_id"):
        await async_resolve_media(hass, ":bad_id")

    dms_device_mock.async_search_directory.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.INVALID_SEARCH_CRITERIA
    )
    with pytest.raises(Unresolvable, match="Invalid query: bad query"):
        await async_resolve_media(hass, "?bad query")

    dms_device_mock.async_browse_metadata.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.CANNOT_PROCESS_REQUEST
    )
    with pytest.raises(BrowseError, match="Server failure: "):
        await async_resolve_media(hass, ":good_id")

    dms_device_mock.async_browse_metadata.side_effect = UpnpError
    with pytest.raises(
        BrowseError, match="Server communication failure: UpnpError(.*)"
    ):
        await async_resolve_media(hass, ":bad_id")


async def test_catch_upnp_connection_error(
    hass: HomeAssistant, dms_device_mock: Mock
) -> None:
    """Test UpnpConnectionError causes the device source to disconnect from the device."""
    # First check the source can be used
    object_id = "foo"
    didl_item = didl_lite.Item(
        id=object_id,
        restricted="false",
        title="Object",
        res=[didl_lite.Resource(uri="foo", protocol_info="http-get:*:audio/mpeg")],
    )
    dms_device_mock.async_browse_metadata.return_value = didl_item
    await async_browse_media(hass, f":{object_id}")
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        object_id, metadata_filter=ANY
    )

    # Cause a UpnpConnectionError when next browsing
    dms_device_mock.async_browse_metadata.side_effect = UpnpConnectionError
    with pytest.raises(
        BrowseError, match="Server disconnected: UpnpConnectionError(.*)"
    ):
        await async_browse_media(hass, f":{object_id}")

    # Clear the error, but the device should be disconnected
    dms_device_mock.async_browse_metadata.side_effect = None
    with pytest.raises(BrowseError, match="DMS is not connected"):
        await async_browse_media(hass, f":{object_id}")


async def test_resolve_media_object(hass: HomeAssistant, dms_device_mock: Mock) -> None:
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
    result = await async_resolve_media(hass, f":{object_id}")
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
    result = await async_resolve_media(hass, f":{object_id}")
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
    result = await async_resolve_media(hass, f":{object_id}")
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
        await async_resolve_media(hass, f":{object_id}")

    # Failure case: resources are not playable
    didl_item = didl_lite.Item(
        id=object_id,
        restricted="false",
        title="Object",
        res=[didl_lite.Resource(uri="internal:thing", protocol_info="internal:*::")],
    )
    dms_device_mock.async_browse_metadata.return_value = didl_item
    with pytest.raises(Unresolvable, match="Object has no playable resources"):
        await async_resolve_media(hass, f":{object_id}")


async def test_resolve_media_path(hass: HomeAssistant, dms_device_mock: Mock) -> None:
    """Test the async_resolve_path method via async_resolve_media."""
    # Path resolution involves searching each component of the path, then
    # browsing the metadata of the final object found.
    path: Final = "path/to/thing"
    object_ids: Final = ["path_id", "to_id", "thing_id"]
    res_url: Final = "foo/bar"
    res_abs_url: Final = f"{MOCK_DEVICE_BASE_URL}/{res_url}"
    res_mime: Final = "audio/mpeg"

    search_directory_result = []
    for ob_id, ob_title in zip(object_ids, path.split("/"), strict=False):
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
    result = await async_resolve_media(hass, f"/{path}")
    assert dms_device_mock.async_search_directory.await_args_list == [
        call(
            parent_id,
            search_criteria=f'@parentID="{parent_id}" and dc:title="{title}"',
            metadata_filter=["id", "upnp:class", "dc:title"],
            requested_count=1,
        )
        for parent_id, title in zip(
            ["0"] + object_ids[:-1], path.split("/"), strict=False
        )
    ]
    assert result.url == res_abs_url
    assert result.mime_type == res_mime

    # Test a path starting with a / (first / is path action, second / is root of path)
    dms_device_mock.async_search_directory.reset_mock()
    dms_device_mock.async_search_directory.side_effect = search_directory_result
    result = await async_resolve_media(hass, f"//{path}")
    assert dms_device_mock.async_search_directory.await_args_list == [
        call(
            parent_id,
            search_criteria=f'@parentID="{parent_id}" and dc:title="{title}"',
            metadata_filter=["id", "upnp:class", "dc:title"],
            requested_count=1,
        )
        for parent_id, title in zip(
            ["0"] + object_ids[:-1], path.split("/"), strict=False
        )
    ]
    assert result.url == res_abs_url
    assert result.mime_type == res_mime


async def test_resolve_path_browsed(hass: HomeAssistant, dms_device_mock: Mock) -> None:
    """Test async_resolve_path: action error results in browsing."""
    path: Final = "path/to/thing"
    object_ids: Final = ["path_id", "to_id", "thing_id"]
    res_url: Final = "foo/bar"
    res_mime: Final = "audio/mpeg"

    # Setup expected calls
    search_directory_result = []
    for ob_id, ob_title in zip(object_ids, path.split("/"), strict=False):
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

    dms_device_mock.async_browse_metadata.return_value = didl_lite.Item(
        id=object_ids[-1],
        restricted="false",
        title="thing",
        res=[didl_lite.Resource(uri=res_url, protocol_info=f"http-get:*:{res_mime}:")],
    )

    # Perform the action to test
    result = await async_resolve_media(hass, path)
    # All levels should have an attempted search
    assert dms_device_mock.async_search_directory.await_args_list == [
        call(
            parent_id,
            search_criteria=f'@parentID="{parent_id}" and dc:title="{title}"',
            metadata_filter=["id", "upnp:class", "dc:title"],
            requested_count=1,
        )
        for parent_id, title in zip(
            ["0"] + object_ids[:-1], path.split("/"), strict=False
        )
    ]
    assert result.didl_metadata.id == object_ids[-1]
    # 2nd level should also be browsed
    assert dms_device_mock.async_browse_direct_children.await_args_list == [
        call("path_id", metadata_filter=["id", "upnp:class", "dc:title"])
    ]


async def test_resolve_path_browsed_nothing(
    hass: HomeAssistant, dms_device_mock: Mock
) -> None:
    """Test async_resolve_path: action error results in browsing, but nothing found."""
    dms_device_mock.async_search_directory.side_effect = UpnpActionError()
    # No children
    dms_device_mock.async_browse_direct_children.side_effect = [
        DmsDevice.BrowseResult([], 0, 0, 0)
    ]
    with pytest.raises(Unresolvable, match="No contents for thing in thing/other"):
        await async_resolve_media(hass, "thing/other")

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
        await async_resolve_media(hass, "thing/other")


async def test_resolve_path_quoted(hass: HomeAssistant, dms_device_mock: Mock) -> None:
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
    with pytest.raises(Unresolvable):
        await async_resolve_media(hass, r'path/quote"back\slash')
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
    hass: HomeAssistant, dms_device_mock: Mock
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
        await async_resolve_media(hass, "thing/other")


async def test_resolve_path_no_such_container(
    hass: HomeAssistant, dms_device_mock: Mock
) -> None:
    """Test async_resolve_path: Explicit check for NO_SUCH_CONTAINER."""
    dms_device_mock.async_search_directory.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.NO_SUCH_CONTAINER
    )
    with pytest.raises(Unresolvable, match="No such container: 0"):
        await async_resolve_media(hass, "thing/other")


async def test_resolve_media_search(hass: HomeAssistant, dms_device_mock: Mock) -> None:
    """Test the async_resolve_search method via async_resolve_media."""
    res_url: Final = "foo/bar"
    res_abs_url: Final = f"{MOCK_DEVICE_BASE_URL}/{res_url}"
    res_mime: Final = "audio/mpeg"

    # No results
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )
    with pytest.raises(Unresolvable, match='Nothing found for dc:title="thing"'):
        await async_resolve_media(hass, '?dc:title="thing"')
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
    result = await async_resolve_media(hass, '?dc:title="thing"')
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
    result = await async_resolve_media(hass, '?dc:title="thing"')
    assert result.url == res_abs_url
    assert result.mime_type == res_mime
    assert result.didl_metadata is didl_item

    # Bad result
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [didl_lite.Descriptor("id", "namespace")], 1, 1, 0
    )
    with pytest.raises(Unresolvable, match="Descriptor.* is not a DidlObject"):
        await async_resolve_media(hass, '?dc:title="thing"')


async def test_browse_media_root(hass: HomeAssistant, dms_device_mock: Mock) -> None:
    """Test async_browse_media with no identifier will browse the root of the device."""
    dms_device_mock.async_browse_metadata.return_value = didl_lite.DidlObject(
        id="0", restricted="false", title="root"
    )
    dms_device_mock.async_browse_direct_children.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )

    # No identifier (first opened in media browser)
    result = await media_source.async_browse_media(hass, f"media-source://{DOMAIN}")
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

    # Only source ID, no object ID
    result = await media_source.async_browse_media(
        hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}"
    )
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
    result = await media_source.async_browse_media(
        hass, f"media-source://{DOMAIN}/{MOCK_SOURCE_ID}/"
    )
    assert result.identifier == f"{MOCK_SOURCE_ID}/:0"
    assert result.title == MOCK_DEVICE_NAME
    dms_device_mock.async_browse_metadata.assert_awaited_once_with(
        "0", metadata_filter=ANY
    )
    dms_device_mock.async_browse_direct_children.assert_awaited_once_with(
        "0", metadata_filter=ANY, sort_criteria=ANY
    )


async def test_browse_media_object(hass: HomeAssistant, dms_device_mock: Mock) -> None:
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

    result = await async_browse_media(hass, f":{object_id}")
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
    for child, title in zip(result.children, child_titles, strict=False):
        assert isinstance(child, BrowseMediaSource)
        assert child.identifier == f"{MOCK_SOURCE_ID}/:{title}_id"
        assert child.title == title
        assert child.can_play
        assert not child.can_expand
        assert not child.children


async def test_browse_object_sort_anything(
    hass: HomeAssistant, dms_device_mock: Mock
) -> None:
    """Test sort criteria for children where device allows anything."""
    dms_device_mock.sort_capabilities = ["*"]

    object_id = "0"
    dms_device_mock.async_browse_metadata.return_value = didl_lite.Container(
        id="0", restricted="false", title="root"
    )
    dms_device_mock.async_browse_direct_children.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )
    await async_browse_media(hass, ":0")

    # Sort criteria should be dlna_dms's default
    dms_device_mock.async_browse_direct_children.assert_awaited_once_with(
        object_id, metadata_filter=ANY, sort_criteria=DLNA_SORT_CRITERIA
    )


async def test_browse_object_sort_superset(
    hass: HomeAssistant, dms_device_mock: Mock
) -> None:
    """Test sorting where device allows superset of integration's criteria."""
    dms_device_mock.sort_capabilities = [
        "dc:title",
        "upnp:originalTrackNumber",
        "upnp:class",
        "upnp:artist",
        "dc:creator",
        "upnp:genre",
    ]

    object_id = "0"
    dms_device_mock.async_browse_metadata.return_value = didl_lite.Container(
        id="0", restricted="false", title="root"
    )
    dms_device_mock.async_browse_direct_children.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )
    await async_browse_media(hass, ":0")

    # Sort criteria should be dlna_dms's default
    dms_device_mock.async_browse_direct_children.assert_awaited_once_with(
        object_id, metadata_filter=ANY, sort_criteria=DLNA_SORT_CRITERIA
    )


async def test_browse_object_sort_subset(
    hass: HomeAssistant, dms_device_mock: Mock
) -> None:
    """Test sorting where device allows subset of integration's criteria."""
    dms_device_mock.sort_capabilities = [
        "dc:title",
        "upnp:class",
    ]

    object_id = "0"
    dms_device_mock.async_browse_metadata.return_value = didl_lite.Container(
        id="0", restricted="false", title="root"
    )
    dms_device_mock.async_browse_direct_children.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )
    await async_browse_media(hass, ":0")

    # Sort criteria should be reduced to only those allowed,
    # and in the order specified by DLNA_SORT_CRITERIA
    expected_criteria = ["+upnp:class", "+dc:title"]
    dms_device_mock.async_browse_direct_children.assert_awaited_once_with(
        object_id, metadata_filter=ANY, sort_criteria=expected_criteria
    )


async def test_browse_media_path(hass: HomeAssistant, dms_device_mock: Mock) -> None:
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

    result = await async_browse_media(hass, title)
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


async def test_browse_media_search(hass: HomeAssistant, dms_device_mock: Mock) -> None:
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

    result = await async_browse_media(hass, f"?{query}")
    assert result.identifier == f"{MOCK_SOURCE_ID}/?{query}"
    assert result.title == "Search results"
    assert result.children

    for obj, child in zip(object_details, result.children, strict=False):
        assert isinstance(child, BrowseMediaSource)
        assert child.identifier == f"{MOCK_SOURCE_ID}/:{obj[0]}"
        assert child.title == obj[1]
        assert not child.children


async def test_browse_search_invalid(
    hass: HomeAssistant, dms_device_mock: Mock
) -> None:
    """Test searching with an invalid query gives a BrowseError."""
    query = "title == FooBar"
    dms_device_mock.async_search_directory.side_effect = UpnpActionError(
        error_code=ContentDirectoryErrorCode.INVALID_SEARCH_CRITERIA
    )
    with pytest.raises(BrowseError, match=f"Invalid query: {query}"):
        await async_browse_media(hass, f"?{query}")


async def test_browse_search_no_results(
    hass: HomeAssistant, dms_device_mock: Mock
) -> None:
    """Test a search with no results does not give an error."""
    query = 'dc:title contains "FooBar"'
    dms_device_mock.async_search_directory.return_value = DmsDevice.BrowseResult(
        [], 0, 0, 0
    )

    result = await async_browse_media(hass, f"?{query}")
    assert result.identifier == f"{MOCK_SOURCE_ID}/?{query}"
    assert result.title == "Search results"
    assert not result.children


async def test_thumbnail(hass: HomeAssistant, dms_device_mock: Mock) -> None:
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

    result = await async_browse_media(hass, "?query")
    assert result.children
    assert result.children[0].thumbnail == f"{MOCK_DEVICE_BASE_URL}/a_thumb.jpg"
    assert result.children[1].thumbnail == f"{MOCK_DEVICE_BASE_URL}/b_thumb.png"
    assert result.children[2].thumbnail is None


async def test_can_play(hass: HomeAssistant, dms_device_mock: Mock) -> None:
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

    result = await async_browse_media(hass, "?query")
    assert result.children
    assert not result.children[0].can_play
    for idx, info_can_play in enumerate(protocol_infos):
        protocol_info, can_play = info_can_play
        assert result.children[idx + 1].can_play is can_play, f"Checked {protocol_info}"
