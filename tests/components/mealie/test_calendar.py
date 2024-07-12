"""Tests for the Mealie calendar."""

from datetime import date
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator


async def test_api_calendar(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the API returns the calendar."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get("/api/calendars")
    assert response.status == HTTPStatus.OK
    data = await response.json()
    assert data == snapshot


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the API returns the calendar."""
    with patch("homeassistant.components.mealie.PLATFORMS", [Platform.CALENDAR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_api_events(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the Mealie calendar view."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(
        "/api/calendars/calendar.mealie_dinner?start=2023-08-01&end=2023-11-01"
    )
    assert mock_mealie_client.get_mealplans.called == 1
    assert mock_mealie_client.get_mealplans.call_args_list[1].args == (
        date(2023, 8, 1),
        date(2023, 11, 1),
    )
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert events == snapshot
