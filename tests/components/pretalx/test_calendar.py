"""Test the pretalx calendar platform."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pretalx.const import DEFAULT_UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import BASE_URL

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.freeze_time("2026-09-15T01:30:00+00:00")
@pytest.mark.usefixtures("mock_pretalx")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the calendar entities, one per room."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_pretalx")
async def test_get_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching all sessions in a time frame."""
    await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "start_date_time": datetime(2026, 9, 15, tzinfo=dt_util.UTC),
            "end_date_time": datetime(2026, 9, 18, tzinfo=dt_util.UTC),
        },
        target={"entity_id": [entity.entity_id for entity in entities]},
        blocking=True,
        return_response=True,
    )

    assert response == snapshot


@pytest.mark.usefixtures("mock_pretalx")
async def test_new_room_added(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a room added in a later schedule creates a new entity."""
    await setup_integration(hass, mock_config_entry)

    def room_count() -> int:
        return len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )

    assert room_count() == 3

    rooms = await async_load_json_object_fixture(hass, "rooms.json", "pretalx")
    rooms["results"].append({"id": 132, "name": {"en": "Cyan Room"}, "description": {}})
    rooms["count"] = 3
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{BASE_URL}/",
        json=await async_load_json_object_fixture(hass, "event.json", "pretalx"),
    )
    aioclient_mock.get(f"{BASE_URL}/rooms/", json=rooms)
    aioclient_mock.get(
        f"{BASE_URL}/submissions/",
        json=await async_load_json_object_fixture(hass, "submissions.json", "pretalx"),
    )

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert room_count() == 4

    # A further refresh without new rooms must not add entities.
    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert room_count() == 4
