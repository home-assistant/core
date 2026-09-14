"""Tests for Shelly camera storage media source."""

from copy import deepcopy
from unittest.mock import AsyncMock, Mock

from aioshelly.const import MODEL_CAMERA
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source import Unresolvable
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import init_integration
from .conftest import MOCK_STORAGE_LIST


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
    assert child.identifier == f"{entry.entry_id}:0"
    assert child.title == "Test name"
    assert child.can_expand is True
    assert child.can_play is False


async def test_root_skips_non_camera(
    hass: HomeAssistant, mock_rpc_device: Mock
) -> None:
    """Test root browsing skips entries without a camera."""
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
        hass, f"media-source://shelly/{entry.entry_id}:0"
    )

    assert result.children is not None
    assert len(result.children) == 8
    assert result.as_dict() == snapshot(exclude=props("media_content_id"))
    by_id = {child.identifier.rsplit(":", 1)[1]: child for child in result.children}
    assert list(by_id) == [
        item["media_id"] for item in reversed(MOCK_STORAGE_LIST["items"])
    ]
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
        hass, f"media-source://shelly/{entry.entry_id}:0"
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


async def test_browse_storage_pagination(
    hass: HomeAssistant, mock_camera_storage: Mock
) -> None:
    """Test browsing follows Storage.List pagination."""
    mock_camera_storage.call_rpc = AsyncMock(
        side_effect=[
            {
                "total": 8,
                "offset": 0,
                "rev": 8,
                "items": MOCK_STORAGE_LIST["items"][:5],
            },
            {
                "total": 8,
                "offset": 5,
                "rev": 8,
                "items": MOCK_STORAGE_LIST["items"][5:],
            },
        ]
    )
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(
        hass, f"media-source://shelly/{entry.entry_id}:0"
    )

    assert result.children is not None
    assert len(result.children) == 8
    assert mock_camera_storage.call_rpc.await_count == 2


async def test_browse_storage_empty(
    hass: HomeAssistant, mock_camera_storage: Mock
) -> None:
    """Test browsing empty storage returns no children."""
    mock_camera_storage.call_rpc = AsyncMock(
        return_value={"total": 0, "offset": 0, "rev": 1, "items": []}
    )
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    result = await media_source.async_browse_media(
        hass, f"media-source://shelly/{entry.entry_id}:0"
    )

    assert result.children == []


@pytest.mark.parametrize(
    ("index", "mime_type"),
    [
        pytest.param(0, "video/mp4", id="video"),
        pytest.param(2, "image/jpeg", id="image"),
    ],
)
async def test_resolve_media(
    hass: HomeAssistant, mock_camera_storage: Mock, index: int, mime_type: str
) -> None:
    """Test resolving storage items returns the pre-signed URL and mime type."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    media_id = MOCK_STORAGE_LIST["items"][index]["media_id"]

    result = await media_source.async_resolve_media(
        hass, f"media-source://shelly/{entry.entry_id}:0:{media_id}", None
    )

    assert result.url == MOCK_STORAGE_LIST["items"][index]["url"]
    assert result.mime_type == mime_type


@pytest.mark.parametrize(
    "identifier",
    [
        pytest.param("bad", id="no_separator"),
        pytest.param("a:b:c:d", id="too_many_parts"),
        pytest.param("missing:0", id="unknown_entry"),
    ],
)
async def test_browse_bad_identifier(
    hass: HomeAssistant, mock_camera_storage: Mock, identifier: str
) -> None:
    """Test browsing with a malformed identifier raises BrowseError."""
    assert await async_setup_component(hass, "media_source", {})
    await init_integration(hass, 3, model=MODEL_CAMERA)

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{identifier}"
        )

    assert excinfo.value.translation_key == "unexpected_identifier"


@pytest.mark.parametrize(
    "template",
    [
        pytest.param("bad", id="no_separator"),
        pytest.param("a:b:c:d", id="too_many_parts"),
        pytest.param("{entry_id}:0", id="folder_identifier"),
        pytest.param("{entry_id}:nan", id="invalid_storage_id"),
        pytest.param("{entry_id}:0:does-not-exist", id="unknown_media"),
    ],
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


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(DeviceConnectionError(), id="connection_error"),
        pytest.param(RpcCallError(999), id="rpc_error"),
    ],
)
async def test_browse_storage_unavailable(
    hass: HomeAssistant, mock_camera_storage: Mock, side_effect: Exception
) -> None:
    """Test browsing storage raises when the device cannot be reached."""
    mock_camera_storage.call_rpc = AsyncMock(side_effect=side_effect)
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{entry.entry_id}:0"
        )

    assert excinfo.value.translation_key == "storage_unavailable"


async def test_browse_storage_auth_error(
    hass: HomeAssistant, mock_camera_storage: Mock
) -> None:
    """Test browsing storage starts reauth on authentication failure."""
    mock_camera_storage.call_rpc = AsyncMock(side_effect=InvalidAuthError)
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{entry.entry_id}:0"
        )

    assert excinfo.value.translation_key == "auth_error"
    assert mock_camera_storage.shutdown.await_count == 1


async def test_browse_storage_private(
    hass: HomeAssistant, mock_camera_storage: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test browsing storage raises when camera privacy mode is enabled."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    new_status = deepcopy(mock_camera_storage.status)
    new_status["camera:0"]["privacy"] = True
    monkeypatch.setattr(mock_camera_storage, "status", new_status)

    with pytest.raises(BrowseError) as excinfo:
        await media_source.async_browse_media(
            hass, f"media-source://shelly/{entry.entry_id}:0"
        )

    assert excinfo.value.translation_key == "storage_private"


async def test_resolve_storage_private(
    hass: HomeAssistant, mock_camera_storage: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test resolving storage raises when camera privacy mode is enabled."""
    assert await async_setup_component(hass, "media_source", {})
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    new_status = deepcopy(mock_camera_storage.status)
    new_status["camera:0"]["privacy"] = True
    monkeypatch.setattr(mock_camera_storage, "status", new_status)
    media_id = MOCK_STORAGE_LIST["items"][0]["media_id"]

    with pytest.raises(Unresolvable) as excinfo:
        await media_source.async_resolve_media(
            hass, f"media-source://shelly/{entry.entry_id}:0:{media_id}", None
        )

    assert excinfo.value.translation_key == "storage_private"
