"""Tests for the UniFi Access image platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from unifi_access_api.models.websocket import (
    LocationUpdateData,
    LocationUpdateV2,
    ThumbnailInfo,
    WebsocketMessage,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator

FRONT_DOOR_IMAGE = "image.front_door_thumbnail"
BACK_DOOR_IMAGE = "image.back_door_thumbnail"


def _get_ws_handlers(
    mock_client: MagicMock,
) -> dict[str, Callable[[WebsocketMessage], Awaitable[None]]]:
    """Extract WebSocket handlers from mock client."""
    return mock_client.start_websocket.call_args[0][0]


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


async def test_image_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test image entities are created with expected state."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.IMAGE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_async_image_with_thumbnail(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test async_image returns bytes when a thumbnail exists from initial load."""
    mock_client.get_thumbnail.return_value = b"fake-image-bytes"

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{FRONT_DOOR_IMAGE}")

    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"fake-image-bytes"
    mock_client.get_thumbnail.assert_awaited_once_with("/preview/front_door.png")


async def test_async_image_without_thumbnail(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test async_image returns empty response when no thumbnail exists."""
    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{BACK_DOOR_IMAGE}")

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_initial_thumbnail_sets_image_last_updated(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test initial thumbnail from API sets image_last_updated immediately."""
    state = hass.states.get(FRONT_DOOR_IMAGE)
    assert state is not None
    assert state.state != "unknown"

    # Back door has no thumbnail, so it should be unknown
    state_back = hass.states.get(BACK_DOOR_IMAGE)
    assert state_back is not None
    assert state_back.state == "unknown"


async def test_handle_coordinator_update_sets_image_last_updated(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WS thumbnail update sets image_last_updated from thumbnail."""
    # Back door starts without thumbnail
    state_before = hass.states.get(BACK_DOOR_IMAGE)
    assert state_before is not None
    assert state_before.state == "unknown"

    handlers = _get_ws_handlers(mock_client)
    await handlers["access.data.device.location_update_v2"](
        LocationUpdateV2(
            event="access.data.device.location_update_v2",
            data=LocationUpdateData(
                id="door-002",
                location_type="DOOR",
                state=None,
                thumbnail=ThumbnailInfo(
                    url="/thumb/door-002.jpg",
                    door_thumbnail_last_update=1700000000,
                ),
            ),
        )
    )
    await hass.async_block_till_done()

    state_after = hass.states.get(BACK_DOOR_IMAGE)
    assert state_after is not None
    assert state_after.state != "unknown"

    # Second update with a newer timestamp should change image_last_updated
    await handlers["access.data.device.location_update_v2"](
        LocationUpdateV2(
            event="access.data.device.location_update_v2",
            data=LocationUpdateData(
                id="door-002",
                location_type="DOOR",
                state=None,
                thumbnail=ThumbnailInfo(
                    url="/thumb/door-002-v2.jpg",
                    door_thumbnail_last_update=1700001000,
                ),
            ),
        )
    )
    await hass.async_block_till_done()

    state_updated = hass.states.get(BACK_DOOR_IMAGE)
    assert state_updated is not None
    assert state_updated.state != state_after.state
