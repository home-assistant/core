"""Test for the smhi image entity."""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pysmhi import SMHIRadar, SmhiRadarException
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.image import async_get_image
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

ENTITY_ID = "image.test_radar"

pytestmark = pytest.mark.parametrize("load_platforms", [[Platform.IMAGE]])


@pytest.fixture
def mock_getrandbits() -> Generator[None]:
    """Mock image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.entity.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_getrandbits")
async def test_image_setup(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for successfully setting up the smhi image."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "load_int")
async def test_image_cached_per_radar_update(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_radar_client: MagicMock,
    get_radar_data: SMHIRadar,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the radar image is fetched once for each radar update."""
    client = await hass_client()

    for _ in range(2):
        resp = await client.get(f"/api/image_proxy/{ENTITY_ID}")
        assert resp.status == HTTPStatus.OK
        assert await resp.read() == b"radar image"
    assert mock_radar_client.async_get_image.call_count == 1

    new_valid_time = datetime(2026, 11, 10, 18, 40, tzinfo=UTC)
    mock_radar_client.async_get_radar.return_value = {
        **get_radar_data,
        "valid_time": new_valid_time,
    }
    mock_radar_client.async_get_image.return_value = b"new radar image"
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == new_valid_time.isoformat()

    resp = await client.get(f"/api/image_proxy/{ENTITY_ID}")
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"new radar image"
    assert mock_radar_client.async_get_image.call_count == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "load_int")
async def test_image_concurrent_requests(
    hass: HomeAssistant,
    mock_radar_client: MagicMock,
) -> None:
    """Test concurrent requests for the same radar update fetch the image once."""
    fetching = asyncio.Event()
    release = asyncio.Event()

    async def _get_image() -> bytes:
        fetching.set()
        await release.wait()
        return b"radar image"

    mock_radar_client.async_get_image.side_effect = _get_image

    requests = [
        hass.async_create_task(async_get_image(hass, ENTITY_ID)) for _ in range(3)
    ]
    await fetching.wait()
    release.set()
    images = await asyncio.gather(*requests)

    assert [image.content for image in images] == [b"radar image"] * 3
    assert mock_radar_client.async_get_image.call_count == 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "load_int")
async def test_image_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_radar_client: MagicMock,
) -> None:
    """Test fetching the radar image fails."""
    mock_radar_client.async_get_image.side_effect = SmhiRadarException("boom")
    client = await hass_client()

    resp = await client.get(f"/api/image_proxy/{ENTITY_ID}")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
