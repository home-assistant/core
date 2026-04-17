"""Tests for the Cyclus NV calendar."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2024-01-09 00:00:00+00:00")
async def test_waste_pickup_calendar(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_cyclus_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Cyclus NV waste pickup calendar."""
    with patch("homeassistant.components.cyclus_nv.PLATFORMS", [Platform.CALENDAR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_api_events(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_cyclus_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the Cyclus NV calendar events."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(
        "/api/calendars/calendar.1234ab_1?start=2024-01-09&end=2024-01-11"
    )
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert len(events) == 1
    assert events == snapshot
