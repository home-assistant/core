"""Tests for the Gatus binary sensor platform."""

import json
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import async_fire_time_changed, load_fixture, snapshot_platform

TEST_ENTRY_ID = "1234567890abcdef1234567890abcdef"


async def test_binary_sensor_setup_and_states(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test standard successful setup and entity snapshots using snapshot_platform."""
    fixture_data = await hass.async_add_executor_job(
        load_fixture, "gatus/statuses_success.json"
    )
    mock_data = json.loads(fixture_data)

    config_entry = await setup_integration(
        hass, mock_gatus_client, mock_data, entry_id=TEST_ENTRY_ID
    )

    entity_registry = er.async_get(hass)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_dynamic_endpoint_discovery(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a new endpoint appearing in a data refresh creates an entity automatically."""
    initial_data = [
        {"key": "service_one", "name": "Service One", "results": [{"success": True}]}
    ]

    await setup_integration(
        hass, mock_gatus_client, initial_data, entry_id=TEST_ENTRY_ID
    )

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator: GatusDataUpdateCoordinator = config_entry.runtime_data
    entity_registry = er.async_get(hass)

    assert (
        entity_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{TEST_ENTRY_ID}_service_one"
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{TEST_ENTRY_ID}_service_two"
        )
        is None
    )

    updated_data = [
        {"key": "service_one", "name": "Service One", "results": [{"success": True}]},
        {"key": "service_two", "name": "Service Two", "results": [{"success": True}]},
    ]

    with patch.object(
        mock_gatus_client,
        "get_endpoints_statuses",
        AsyncMock(return_value=updated_data),
    ):
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{TEST_ENTRY_ID}_service_two"
        )
        is not None
    )


async def test_binary_sensor_missing_data(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor behavior when endpoint data or results are missing."""
    missing_data = [{"key": "service_one", "name": "Service One", "results": []}]

    await setup_integration(
        hass, mock_gatus_client, missing_data, entry_id=TEST_ENTRY_ID
    )

    state = hass.states.get("binary_sensor.service_one")
    assert state is not None
    assert state.state == "unknown"

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator: GatusDataUpdateCoordinator = config_entry.runtime_data

    with patch.object(
        mock_gatus_client,
        "get_endpoints_statuses",
        AsyncMock(return_value=[]),
    ):
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.service_one")
    assert state is not None
    assert state.state == "unavailable"
