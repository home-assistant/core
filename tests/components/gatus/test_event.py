"""Tests for the Gatus event platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from gatus_api import EndpointStatus, Event, Result
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_event_setup_and_states(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test standard successful setup and entity snapshots using snapshot_platform."""
    with patch("homeassistant.components.gatus._PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


def _to_endpoint_statuses(raw_data: list[dict[str, Any]]) -> list[EndpointStatus]:
    return [
        EndpointStatus(
            key=ep["key"],
            name=ep["name"],
            group=ep.get("group"),
            results=[
                Result(
                    success=r["success"],
                    status=r.get("status"),
                    duration=r.get("duration"),
                )
                for r in ep.get("results", [])
            ],
            events=[
                Event(
                    type=ev["type"],
                    timestamp=ev.get("timestamp"),
                )
                for ev in ep.get("events", [])
            ],
        )
        for ep in raw_data
    ]


async def test_event_dynamic_update(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that event entities trigger when new event data arrives."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("event.core_backend_service_status_event")
    assert state is not None

    mock_data = [
        {
            "key": "backend_service",
            "name": "Backend Service",
            "group": "Core",
            "results": [{"success": True, "status": 200, "duration": 45000000}],
            "events": [
                {
                    "type": "HEALTHY",
                    "timestamp": "2026-08-10T17:00:00Z",
                }
            ],
        }
    ]

    mock_gatus_client.get_endpoints_statuses.return_value = _to_endpoint_statuses(
        mock_data
    )

    freezer.tick(300)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("event.core_backend_service_status_event")
    assert state is not None
    assert state.attributes.get("event_type") == "healthy"
