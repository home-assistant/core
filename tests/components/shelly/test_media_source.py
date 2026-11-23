"""Tests for Shelly camera storage media source."""

from typing import Any
from unittest.mock import AsyncMock, Mock, PropertyMock

from aioshelly.const import MODEL_CAMERA
from aioshelly.exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    NotInitialized,
    RpcCallError,
)
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source import Unresolvable
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import init_integration
from .conftest import MOCK_CAMERA_STATUS, MOCK_STORAGE_ITEMS

ENTRY_ID = "01JSHELLYCAMERA0000000000"


async def test_root_lists_camera(
    hass: HomeAssistant, mock_camera_storage: Mock
) -> None:
    """Test root browsing lists the camera storage folder."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(hass, "media-source://shelly")

    assert result.children is not None
    assert len(result.children) == 1
    child = result.children[0]
    assert child.identifier == entry.entry_id
    assert child.title == "Test name"
    assert child.can_expand is True
    assert child.can_play is False


async def test_root_without_camera_entity(
    hass: HomeAssistant,
    mock_camera_storage: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the storage folder has no thumbnail when RTSP is disabled."""
    monkeypatch.setitem(mock_camera_storage.config["camera:0"]["rtsp"], "enable", False)
    assert await async_setup_component(hass, "media_source", {})
    await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(hass, "media-source://shelly")

    assert result.children is not None
    assert len(result.children) == 1
    assert result.children[0].thumbnail is None


@pytest.mark.parametrize(
    "status",
    [
        MOCK_CAMERA_STATUS,
        {**MOCK_CAMERA_STATUS, "storage:0": {"present": False, "active": False}},
        {
            **MOCK_CAMERA_STATUS,
            "storage:0": {"present": True, "active": False, "fs_free": 0},
        },
    ],
)
async def test_root_skips_inactive_storage(
    hass: HomeAssistant,
    mock_camera_storage: Mock,
    monkeypatch: pytest.MonkeyPatch,
    status: dict[str, Any],
) -> None:
    """Test root browsing skips devices without active storage."""
    monkeypatch.setattr(mock_camera_storage, "status", status)
    assert await async_setup_component(hass, "media_source", {})
    await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(hass, "media-source://shelly")

    assert result.children == []


async def test_root_skips_non_camera(
    hass: HomeAssistant, mock_rpc_device: Mock
) -> None:
    """Test root browsing skips devices without storage."""
    assert await async_setup_component(hass, "media_source", {})
    await init_integration(hass, 2)

    result = await media_source.async_browse_media(hass, "media-source://shelly")

    assert result.children == []


async def test_sleeping_device_is_ignored(
    hass: HomeAssistant, mock_rpc_device: Mock
) -> None:
    """Test a sleeping device is not listed and its status is never read."""
    type(mock_rpc_device).status = PropertyMock(side_effect=NotInitialized)
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 2, sleep_period=1000)

    result = await media_source.async_browse_media(hass, "media-source://shelly")

    assert result.children == []

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{entry.entry_id}"
        )

    assert excinfo.value.translation_key == "unexpected_identifier"


async def test_browse_storage(
    hass: HomeAssistant, mock_camera_storage: Mock, snapshot: SnapshotAssertion
) -> None:
    """Test browsing camera storage lists items sorted by timestamp."""
    await hass.config.async_set_time_zone("UTC")
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA, entry_id=ENTRY_ID)

    result = await media_source.async_browse_media(
        hass, f"media-source://shelly/{entry.entry_id}"
    )

    assert result.as_dict() == snapshot(exclude=props("media_content_id"))
    assert [child.identifier for child in result.children] == [
        f"{ENTRY_ID}:{item['media_id']}" for item in reversed(MOCK_STORAGE_ITEMS)
    ]


async def test_browse_storage_empty(
    hass: HomeAssistant, mock_camera_storage: Mock
) -> None:
    """Test browsing empty storage returns no children."""
    mock_camera_storage.storage_list = AsyncMock(return_value=[])
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(
        hass, f"media-source://shelly/{entry.entry_id}"
    )

    assert result.children == []


@pytest.mark.parametrize(
    ("index", "expected_path", "mime_type"),
    [
        (
            0,
            "11111111-1111-1111-1111-111111111111/aaaa1111/MOV_0001.mp4",
            "video/mp4",
        ),
        (
            2,
            "33333333-3333-3333-3333-333333333333/cccc3333/IMG_0003.jpg",
            "image/jpeg",
        ),
    ],
)
async def test_resolve_media(
    hass: HomeAssistant,
    mock_camera_storage: Mock,
    index: int,
    expected_path: str,
    mime_type: str,
) -> None:
    """Test resolving storage items returns a proxy URL and mime type."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    media_id = MOCK_STORAGE_ITEMS[index]["media_id"]

    result = await media_source.async_resolve_media(
        hass, f"media-source://shelly/{entry.entry_id}:{media_id}", None
    )

    assert result.url == f"/api/shelly/storage/{entry.entry_id}/{expected_path}"
    assert result.mime_type == mime_type


async def test_item_outside_storage(
    hass: HomeAssistant, mock_camera_storage: Mock
) -> None:
    """Test items with URLs outside device storage are not proxied."""
    mock_camera_storage.storage_list = AsyncMock(
        return_value=[
            {
                **MOCK_STORAGE_ITEMS[0],
                "url": "http://example.com/storage/MOV_0001.mp4",
            },
            {**MOCK_STORAGE_ITEMS[1], "thumbnail_url": "/settings/thumb_0002.jpg"},
        ]
    )
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(
        hass, f"media-source://shelly/{entry.entry_id}"
    )

    assert [(child.identifier, child.thumbnail) for child in result.children] == [
        (f"{entry.entry_id}:{MOCK_STORAGE_ITEMS[1]['media_id']}", None)
    ]

    with pytest.raises(Unresolvable) as excinfo:
        await media_source.async_resolve_media(
            hass,
            f"media-source://shelly/{entry.entry_id}:{MOCK_STORAGE_ITEMS[0]['media_id']}",
            None,
        )

    assert excinfo.value.translation_key == "unexpected_identifier"


@pytest.mark.parametrize("template", ["bad", "a:b:c:d", "{entry_id}:0"])
async def test_browse_bad_identifier(
    hass: HomeAssistant, mock_camera_storage: Mock, template: str
) -> None:
    """Test browsing with a malformed identifier raises BrowseError."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{template.format(entry_id=entry.entry_id)}"
        )

    assert excinfo.value.translation_key == "unexpected_identifier"


@pytest.mark.parametrize(
    "template",
    ["bad", "a:b:c:d", "{entry_id}", "{entry_id}:", "{entry_id}:does-not-exist"],
)
async def test_resolve_bad_identifier(
    hass: HomeAssistant, mock_camera_storage: Mock, template: str
) -> None:
    """Test resolving with a malformed identifier raises Unresolvable."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    with pytest.raises(Unresolvable) as excinfo:
        await media_source.async_resolve_media(
            hass,
            f"media-source://shelly/{template.format(entry_id=entry.entry_id)}",
            None,
        )

    assert excinfo.value.translation_key == "unexpected_identifier"


async def test_browse_storage_inactive(
    hass: HomeAssistant, mock_camera_storage: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test browsing raises without querying the device when storage is inactive."""
    monkeypatch.setattr(mock_camera_storage, "status", MOCK_CAMERA_STATUS)
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{entry.entry_id}"
        )

    assert excinfo.value.translation_key == "storage_unavailable"
    assert mock_camera_storage.storage_list.await_count == 0


async def test_resolve_storage_inactive(
    hass: HomeAssistant, mock_camera_storage: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test resolving raises without querying the device when storage is inactive."""
    monkeypatch.setattr(mock_camera_storage, "status", MOCK_CAMERA_STATUS)
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    media_id = MOCK_STORAGE_ITEMS[0]["media_id"]

    with pytest.raises(Unresolvable) as excinfo:
        await media_source.async_resolve_media(
            hass, f"media-source://shelly/{entry.entry_id}:{media_id}", None
        )

    assert excinfo.value.translation_key == "storage_unavailable"
    assert mock_camera_storage.storage_list.await_count == 0


@pytest.mark.parametrize("side_effect", [DeviceConnectionError(), RpcCallError(999)])
async def test_browse_storage_unavailable(
    hass: HomeAssistant, mock_camera_storage: Mock, side_effect: Exception
) -> None:
    """Test browsing storage raises when the device cannot be reached."""
    mock_camera_storage.storage_list = AsyncMock(side_effect=side_effect)
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{entry.entry_id}"
        )

    assert excinfo.value.translation_key == "storage_unavailable"


async def test_browse_storage_auth_error(
    hass: HomeAssistant, mock_camera_storage: Mock
) -> None:
    """Test browsing storage starts reauth on authentication failure."""
    mock_camera_storage.storage_list = AsyncMock(side_effect=InvalidAuthError)
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{entry.entry_id}"
        )

    assert excinfo.value.translation_key == "auth_error"
    assert mock_camera_storage.shutdown.await_count == 1
