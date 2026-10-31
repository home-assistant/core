"""Tests for the System Bridge media player platform."""

import base64
from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from systembridgeconnector.models.media_control import MediaAction, MediaControl
from systembridgeconnector.models.modules import Module
from systembridgeconnector.models.modules.media import Media

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "media_player.hostname_media"


@pytest.fixture(autouse=True)
def media_player_only() -> Generator[None]:
    """Enable only the media player platform."""
    with patch(
        "homeassistant.components.system_bridge.PLATFORMS",
        [Platform.MEDIA_PLAYER],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_media_player_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the media player platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "service_data", "expected"),
    [
        pytest.param(
            SERVICE_MEDIA_PLAY,
            {},
            MediaControl(action=MediaAction.PLAY.value),
            id="play",
        ),
        pytest.param(
            SERVICE_MEDIA_PAUSE,
            {},
            MediaControl(action=MediaAction.PAUSE.value),
            id="pause",
        ),
        pytest.param(
            SERVICE_MEDIA_STOP,
            {},
            MediaControl(action=MediaAction.STOP.value),
            id="stop",
        ),
        pytest.param(
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {},
            MediaControl(action=MediaAction.PREVIOUS.value),
            id="previous",
        ),
        pytest.param(
            SERVICE_MEDIA_NEXT_TRACK,
            {},
            MediaControl(action=MediaAction.NEXT.value),
            id="next",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_control(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    service: str,
    service_data: dict[str, Any],
    expected: MediaControl,
) -> None:
    """Test media player actions send the matching media control."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_websocket_client.media_control.assert_awaited_once_with(expected)


async def test_media_player_image_data_url(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test media player entity picture with a data URL thumbnail and updates."""
    b64_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    png_bytes = base64.b64decode(b64_png)
    data_url_png = f"data:image/png;base64,{b64_png}"

    coordinator = init_integration.runtime_data
    await coordinator.async_handle_module(
        Module.MEDIA,
        Media(
            title="Test Song",
            thumbnail=data_url_png,
        ),
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    entity_picture = state.attributes.get("entity_picture")
    assert entity_picture is not None
    assert entity_picture.startswith(f"/api/media_player_proxy/{ENTITY_ID}?")

    client = await hass_client_no_auth()
    resp = await client.get(entity_picture)
    assert resp.status == HTTPStatus.OK
    assert resp.headers["Content-Type"] == "image/png"
    assert await resp.read() == png_bytes

    # Update with a different thumbnail (JPEG) and verify cache token and image change
    b64_jpeg = (
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP///////////////////////////////////"
        "///////////////////////////////////////////////////wgALCAABAAEBAREA"
        "/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
    )
    jpeg_bytes = base64.b64decode(b64_jpeg)
    data_url_jpeg = f"data:image/jpeg;base64,{b64_jpeg}"

    await coordinator.async_handle_module(
        Module.MEDIA,
        Media(
            title="Another Song",
            thumbnail=data_url_jpeg,
        ),
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    entity_picture_updated = state.attributes.get("entity_picture")
    assert entity_picture_updated is not None
    assert entity_picture_updated != entity_picture

    cache_1 = parse_qs(urlsplit(entity_picture).query)["cache"][0]
    cache_2 = parse_qs(urlsplit(entity_picture_updated).query)["cache"][0]
    assert cache_1 != cache_2

    resp = await client.get(entity_picture_updated)
    assert resp.status == HTTPStatus.OK
    assert resp.headers["Content-Type"] == "image/jpeg"
    assert await resp.read() == jpeg_bytes

    # Update with thumbnail cleared and verify entity_picture is removed
    await coordinator.async_handle_module(
        Module.MEDIA,
        Media(
            title="Track Without Artwork",
            thumbnail=None,
        ),
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("entity_picture") is None


async def test_media_player_image_http_url(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test media player entity picture with an HTTP URL thumbnail."""
    coordinator = init_integration.runtime_data
    await coordinator.async_handle_module(
        Module.MEDIA,
        Media(
            title="Test Song",
            thumbnail="https://example.com/cover.jpg",
        ),
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    entity_picture = state.attributes.get("entity_picture")
    assert entity_picture is not None
    assert entity_picture.startswith(f"/api/media_player_proxy/{ENTITY_ID}?")

    client = await hass_client_no_auth()
    with patch(
        "homeassistant.components.media_player.MediaPlayerEntity.async_get_media_image",
        return_value=(b"image_bytes", "image/jpeg"),
    ) as mock_get_image:
        resp = await client.get(entity_picture)
        assert resp.status == HTTPStatus.OK
        assert resp.headers["Content-Type"] == "image/jpeg"
        assert await resp.read() == b"image_bytes"
        mock_get_image.assert_called_once()


@pytest.mark.parametrize(
    "thumbnail",
    [
        pytest.param("data:text/plain;base64,aGVsbG8=", id="unsupported_mime"),
        pytest.param("data:image/png;base64,invalid!@#$", id="invalid_base64"),
        pytest.param("data:image/png,not_base64", id="missing_base64"),
        pytest.param("invalid_string", id="invalid_string"),
        pytest.param(None, id="none"),
    ],
)
async def test_media_player_image_invalid_or_none(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    thumbnail: str | None,
) -> None:
    """Test media player entity picture is absent for invalid thumbnails."""
    coordinator = init_integration.runtime_data
    await coordinator.async_handle_module(
        Module.MEDIA,
        Media(
            title="Test Song",
            thumbnail=thumbnail,
        ),
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert "entity_picture" not in state.attributes

    client = await hass_client()
    resp = await client.get(f"/api/media_player_proxy/{ENTITY_ID}")
    assert resp.status == HTTPStatus.NOT_FOUND
