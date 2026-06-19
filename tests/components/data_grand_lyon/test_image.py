"""Tests for the Data Grand Lyon image platform."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
import io
from unittest.mock import AsyncMock, patch
import zipfile

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import MOCK_PICTOGRAM_SVG

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import ClientSessionGenerator

IMAGE_ENTITY_ID = "image.c3_stop_100_line_pictogram"


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock the image access token, which is normally randomized."""
    with patch(
        "homeassistant.components.image.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


@pytest.mark.freeze_time("2026-04-10T14:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test all image entities (state, attributes, registry)."""
    with patch("homeassistant.components.data_grand_lyon.PLATFORMS", [Platform.IMAGE]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2026-04-10T14:00:00+00:00")
async def test_image_served(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test the SVG pictogram bytes are served with the right content type."""
    with patch("homeassistant.components.data_grand_lyon.PLATFORMS", [Platform.IMAGE]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{IMAGE_ENTITY_ID}")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/svg+xml"
    assert await resp.read() == MOCK_PICTOGRAM_SVG


@pytest.mark.freeze_time("2026-04-10T14:00:00+00:00")
async def test_image_update(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test the image is refreshed when the pictogram bytes change."""
    with patch("homeassistant.components.data_grand_lyon.PLATFORMS", [Platform.IMAGE]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Use the (mocked, deterministic) image access token so the request keeps
    # working after the clock is advanced past the auth token expiry.
    image_url = f"/api/image_proxy/{IMAGE_ENTITY_ID}?token=1"
    client = await hass_client()
    resp = await client.get(image_url)
    assert await resp.read() == MOCK_PICTOGRAM_SVG

    state = hass.states.get(IMAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "2026-04-10T14:00:00+00:00"

    updated_svg = b'<svg xmlns="http://www.w3.org/2000/svg"><text>C3 v2</text></svg>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("C3_complet.svg", updated_svg)
    mock_tcl_client.get_tcl_line_pictograms_zip.return_value = buffer.getvalue()

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    new_time = dt_util.utcnow()

    resp = await client.get(image_url)
    assert await resp.read() == updated_svg

    state = hass.states.get(IMAGE_ENTITY_ID)
    assert state is not None
    assert state.state == new_time.isoformat()


async def test_pictogram_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test the image is unavailable when no pictogram matches the line."""
    mock_tcl_client.get_tcl_line_pictograms.return_value = []
    with patch("homeassistant.components.data_grand_lyon.PLATFORMS", [Platform.IMAGE]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(IMAGE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_pictogram_failure_does_not_break_other_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """A pictogram fetch failure must not block setup nor the core sensors."""
    mock_tcl_client.get_tcl_line_pictograms_zip.side_effect = ClientConnectionError(
        "API down"
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    departure = hass.states.get("sensor.c3_stop_100_next_departure_1")
    assert departure is not None
    assert departure.state != STATE_UNAVAILABLE

    image = hass.states.get(IMAGE_ENTITY_ID)
    assert image is not None
    assert image.state == STATE_UNAVAILABLE
