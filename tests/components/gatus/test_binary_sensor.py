"""Tests for the Gatus binary sensor platform."""

import json
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import load_fixture, snapshot_platform


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

    config_entry = await setup_integration(hass, mock_gatus_client, mock_data)

    entity_registry = er.async_get(hass)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_binary_sensor_edge_cases(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
) -> None:
    """Test fallback fallthroughs: missing metadata, empty results, and data loss."""
    fixture_data = await hass.async_add_executor_job(
        load_fixture, "gatus/statuses_edge_cases.json"
    )
    mock_data = json.loads(fixture_data)

    config_entry = await setup_integration(hass, mock_gatus_client, mock_data)

    unknown_state = hass.states.get("binary_sensor.gatus_server_unknown_unknown")
    assert unknown_state is not None

    assert unknown_state.name == "Gatus Server Unknown Unknown"

    no_results_state = hass.states.get("binary_sensor.gatus_server_test_empty_results")
    assert no_results_state is not None
    assert no_results_state.state == STATE_OFF
    assert no_results_state.attributes["hostname"] == "fallback.local"
    assert no_results_state.attributes["status_code"] == 503

    coordinator = config_entry.runtime_data
    coordinator.data = []
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    lost_state = hass.states.get("binary_sensor.gatus_server_unknown_unknown")
    assert lost_state is not None
    assert lost_state.state == STATE_UNKNOWN


async def test_binary_sensor_additional_coverage(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
) -> None:
    """Test specific code path edge cases (missing init data, empty results list, and response body attributes)."""
    fixture_data = await hass.async_add_executor_job(
        load_fixture, "gatus/statuses_coverage.json"
    )
    custom_mock_data = json.loads(fixture_data)

    await setup_integration(hass, mock_gatus_client, custom_mock_data)

    backend_state = hass.states.get("binary_sensor.gatus_server_core_backend")
    assert backend_state is not None
    assert backend_state.attributes.get("response_body") == "custom response payload"

    empty_state = hass.states.get("binary_sensor.gatus_server_core_empty")
    assert empty_state is not None
    assert empty_state.state == STATE_UNKNOWN
