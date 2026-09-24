"""Tests for Shelly camera storage media source."""

from typing import Any
from unittest.mock import AsyncMock, Mock

from aioshelly.const import MODEL_CAMERA
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source import Unresolvable
from homeassistant.components.shelly.const import CONF_SLEEP_PERIOD
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import init_integration
from .conftest import MOCK_CAMERA_STATUS, MOCK_STORAGE_ITEMS


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


async def test_browse_storage(
    hass: HomeAssistant, mock_camera_storage: Mock, snapshot: SnapshotAssertion
) -> None:
    """Test browsing camera storage lists items sorted by timestamp."""
    await hass.config.async_set_time_zone("UTC")
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(
        hass, f"media-source://shelly/{entry.entry_id}"
    )

    assert result.children is not None
    assert len(result.children) == 8
    assert result.as_dict() == snapshot(exclude=props("media_content_id"))
    by_id = {child.identifier.rsplit(":", 1)[1]: child for child in result.children}
    assert list(by_id) == [item["media_id"] for item in reversed(MOCK_STORAGE_ITEMS)]
    assert "motion_detected" in by_id["88888888-8888-8888-8888-888888888888"].title
    assert "5s" in by_id["88888888-8888-8888-8888-888888888888"].title
    assert "manual" in by_id["44444444-4444-4444-4444-444444444444"].title


async def test_browse_storage_relative_thumbnail(
    hass: HomeAssistant, mock_camera_storage: Mock
) -> None:
    """Test relative thumbnail URLs are prefixed with the device address."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(
        hass, f"media-source://shelly/{entry.entry_id}"
    )

    assert result.children is not None
    by_id = {child.identifier.rsplit(":", 1)[1]: child for child in result.children}
    assert (
        by_id["22222222-2222-2222-2222-222222222222"].thumbnail
        == "http://192.168.1.37/storage/0/bbbb2222/thumb_0002.jpg"
    )
    assert (
        by_id["11111111-1111-1111-1111-111111111111"].thumbnail
        == "http://192.168.1.37/storage/0/aaaa1111/thumb_0001.jpg"
    )


async def test_browse_storage_empty(
    hass: HomeAssistant, mock_camera_storage: Mock
) -> None:
    """Test browsing empty storage returns no children."""
    mock_camera_storage.get_storage_list = AsyncMock(return_value=[])
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(
        hass, f"media-source://shelly/{entry.entry_id}"
    )

    assert result.children == []


@pytest.mark.parametrize(
    ("index", "expected_url", "mime_type"),
    [
        (0, "http://192.168.1.37/storage/0/aaaa1111/MOV_0001.mp4", "video/mp4"),
        (2, "http://192.168.1.37/storage/0/cccc3333/IMG_0003.jpg", "image/jpeg"),
    ],
)
async def test_resolve_media(
    hass: HomeAssistant,
    mock_camera_storage: Mock,
    index: int,
    expected_url: str,
    mime_type: str,
) -> None:
    """Test resolving storage items returns an absolute URL and mime type."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    media_id = MOCK_STORAGE_ITEMS[index]["media_id"]

    result = await media_source.async_resolve_media(
        hass, f"media-source://shelly/{entry.entry_id}:{media_id}", None
    )

    assert result.url == expected_url
    assert result.mime_type == mime_type


@pytest.mark.parametrize(
    ("port", "expected_url"),
    [
        (8080, "http://192.168.1.37:8080/storage/0/aaaa1111/MOV_0001.mp4"),
        (443, "https://192.168.1.37/storage/0/aaaa1111/MOV_0001.mp4"),
    ],
)
async def test_resolve_media_device_port(
    hass: HomeAssistant, mock_camera_storage: Mock, port: int, expected_url: str
) -> None:
    """Test relative URLs use the scheme and port the device is reachable on."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(
        hass,
        3,
        model=MODEL_CAMERA,
        data={
            CONF_HOST: "192.168.1.37",
            CONF_PORT: port,
            CONF_SLEEP_PERIOD: 0,
            CONF_MODEL: MODEL_CAMERA,
        },
    )
    media_id = MOCK_STORAGE_ITEMS[0]["media_id"]

    result = await media_source.async_resolve_media(
        hass, f"media-source://shelly/{entry.entry_id}:{media_id}", None
    )

    assert result.url == expected_url


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
    assert mock_camera_storage.get_storage_list.await_count == 0


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
    assert mock_camera_storage.get_storage_list.await_count == 0


@pytest.mark.parametrize("side_effect", [DeviceConnectionError(), RpcCallError(999)])
async def test_browse_storage_unavailable(
    hass: HomeAssistant, mock_camera_storage: Mock, side_effect: Exception
) -> None:
    """Test browsing storage raises when the device cannot be reached."""
    mock_camera_storage.get_storage_list = AsyncMock(side_effect=side_effect)
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
    mock_camera_storage.get_storage_list = AsyncMock(side_effect=InvalidAuthError)
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{entry.entry_id}"
        )

    assert excinfo.value.translation_key == "auth_error"
    assert mock_camera_storage.shutdown.await_count == 1
