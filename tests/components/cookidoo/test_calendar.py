"""Test for calendar platform of the Cookidoo integration."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def calendar_only() -> Generator[None]:
    """Enable only the calendar platform."""
    with patch(
        "homeassistant.components.cookidoo.PLATFORMS",
        [Platform.CALENDAR],
    ):
        yield


@pytest.mark.usefixtures("mock_cookidoo_client")
async def test_calendar(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of calendar platform."""

    with patch("homeassistant.components.cookidoo.PLATFORMS", [Platform.CALENDAR]):
        await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, cookidoo_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("mock_cookidoo_client")
async def test_get_events(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching events from Cookidoo calendar."""

    with patch("homeassistant.components.cookidoo.PLATFORMS", [Platform.CALENDAR]):
        await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    entities = er.async_entries_for_config_entry(
        entity_registry, cookidoo_config_entry.entry_id
    )
    assert len(entities) == 1
    entity_id = entities[0].entity_id

    resp = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "start_date_time": datetime(2025, 3, 4, tzinfo=UTC),
            "end_date_time": datetime(2025, 3, 6, tzinfo=UTC),
        },
        target={"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )

    assert resp == snapshot
