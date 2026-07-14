"""Tests for the Gatus binary sensor platform."""

from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from gatus_api import EndpointStatus, GatusClientError, Result
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)


async def test_binary_sensor_setup_and_states(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test standard successful setup and entity snapshots using snapshot_platform."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


def _to_endpoint_statuses(raw_data: list[dict[str, Any]]) -> list[EndpointStatus]:
    return [
        EndpointStatus(
            key=ep["key"],
            name=ep["name"],
            group=ep.get("group"),
            results=[
                Result(success=r["success"], status=r["status"])
                for r in ep.get("results", [])
            ],
        )
        for ep in raw_data
    ]


async def test_binary_sensor_dynamic_update(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the binary sensor entity updates when the mock client returns new data."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("binary_sensor.core_backend_service")
    assert state is not None
    assert state.state == "on"

    mock_data = await async_load_json_array_fixture(hass, "gatus/group.json")

    mock_gatus_client.get_endpoints_statuses.return_value = _to_endpoint_statuses(
        mock_data
    )

    freezer.tick(300)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.core_backend_service")
    assert state.state == "off"


async def test_binary_sensor_no_group(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the binary sensor entity is created correctly when an endpoint has no group."""
    mock_data = await async_load_json_array_fixture(hass, "gatus/no_group.json")

    mock_gatus_client.get_endpoints_statuses.return_value = _to_endpoint_statuses(
        mock_data
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.backend_service")
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_client_error(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a client exception cleanly marks entities as unavailable."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("binary_sensor.core_backend_service")
    assert state is not None
    assert state.state == "on"

    mock_gatus_client.get_endpoints_statuses.side_effect = GatusClientError

    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.core_backend_service")
    assert state.state == "unavailable"


async def test_binary_sensor_empty_results(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an endpoint with empty results is treated as unavailable."""
    mock_gatus_client.get_endpoints_statuses.return_value = [
        EndpointStatus(
            key="backend_service",
            name="Backend Service",
            group=None,
            results=[],
        )
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.backend_service")
    assert state is not None
    assert state.state == "unavailable"

    # Verify underlying properties return None directly on empty results
    entity = hass.data["binary_sensor"].get_entity("binary_sensor.backend_service")
    assert entity is not None
    assert entity.latest_result is None
    assert entity.is_on is None


async def test_binary_sensor_missing_status(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an endpoint with a result missing a status code is handled correctly."""
    mock_gatus_client.get_endpoints_statuses.return_value = [
        EndpointStatus(
            key="backend_service",
            name="Backend Service",
            group=None,
            results=[Result(success=False, status=None)],
        )
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.backend_service")
    assert state is not None
    assert state.state == "off"
