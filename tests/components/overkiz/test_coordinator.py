"""Tests for the Overkiz data update coordinator."""

from unittest.mock import Mock

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, ExecutionState
from pyoverkiz.exceptions import (
    InvalidEventListenerIdException,
    MaintenanceException,
    ServiceUnavailableException,
    TooManyConcurrentRequestsException,
    TooManyRequestsException,
)
import pytest

from homeassistant.components.overkiz.const import (
    DOMAIN,
    EVENT_EXECUTION_FAILED,
    UPDATE_INTERVAL,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import build_event

from tests.common import async_capture_events, async_fire_time_changed

TEMPERATURE_SENSOR = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#2",
    "sensor.maple_residence_garden_radiator_bathroom_temperature_sensor_temperature",
)

SHUTTER = FixtureDevice(
    "setup/cloud_somfy_tahoma_switch_europe.json",
    "io://1234-5678-1698/0",
    "cover.somfy_connected_roller_shutter",
)


@pytest.mark.parametrize(
    "exception",
    [
        TooManyConcurrentRequestsException("Too many concurrent requests"),
        TooManyRequestsException("Too many requests"),
        MaintenanceException("Server is down for maintenance"),
        ServiceUnavailableException("Server is unavailable"),
        InvalidEventListenerIdException("Invalid event listener id"),
        TimeoutError("Timed out"),
        ClientConnectorError(Mock(), Mock()),
    ],
    ids=[
        "too_many_concurrent_requests",
        "too_many_requests",
        "maintenance",
        "service_unavailable",
        "invalid_event_listener_id",
        "timeout",
        "client_connector_error",
    ],
)
async def test_transient_error_is_retried(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Transient errors are handled cleanly: entities go unavailable, then recover."""
    await setup_overkiz_integration(fixture=TEMPERATURE_SENSOR.fixture)

    initial_state = hass.states.get(TEMPERATURE_SENSOR.entity_id)
    assert initial_state.state != STATE_UNAVAILABLE

    # A transient error during a refresh makes the entities unavailable.
    mock_client.fetch_events.side_effect = exception
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == STATE_UNAVAILABLE

    # Once the server recovers, the next refresh restores the entities.
    mock_client.fetch_events.side_effect = None
    mock_client.fetch_events.return_value = []
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_SENSOR.entity_id).state == initial_state.state


async def test_execution_failure_fires_event(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """When an execution fails, an overkiz_execution_failed event is fired."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    # Pre-populate the coordinator's execution tracking
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data.coordinator
    coordinator.executions["exec-1"] = {
        "device_url": SHUTTER.device_url,
        "command_name": "setClosure",
    }

    events = async_capture_events(hass, EVENT_EXECUTION_FAILED)

    mock_client.queue_events(
        [
            build_event(
                EventName.EXECUTION_STATE_CHANGED.value,
                device_url=SHUTTER.device_url,
                exec_id="exec-1",
                new_state=ExecutionState.FAILED.value,
                failure_type="TRANSMISSION_ERROR",
            )
        ]
    )
    await coordinator.async_refresh()

    assert len(events) == 1
    event_data = events[0].data
    assert event_data["exec_id"] == "exec-1"
    assert event_data["device_url"] == SHUTTER.device_url
    assert event_data["command_name"] == "setClosure"
    assert event_data["failure_type"] == "TRANSMISSION_ERROR"
    assert event_data["failure_type_code"] is None

    # Execution is cleaned up after failure
    assert "exec-1" not in coordinator.executions


async def test_execution_failure_unknown_exec_id_is_ignored(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An execution state change for an unknown exec_id is silently ignored."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data.coordinator

    events = async_capture_events(hass, EVENT_EXECUTION_FAILED)

    mock_client.queue_events(
        [
            build_event(
                EventName.EXECUTION_STATE_CHANGED.value,
                device_url=SHUTTER.device_url,
                exec_id="unknown-exec-id",
                new_state=ExecutionState.FAILED.value,
            )
        ]
    )
    await coordinator.async_refresh()

    # No event should be fired for unknown executions
    assert len(events) == 0
    assert "unknown-exec-id" not in coordinator.executions


async def test_execution_failure_uses_unknown_fallbacks(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Missing failure metadata falls back to 'unknown'."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data.coordinator
    coordinator.executions["exec-1"] = {}

    events = async_capture_events(hass, EVENT_EXECUTION_FAILED)

    mock_client.queue_events(
        [
            build_event(
                EventName.EXECUTION_STATE_CHANGED.value,
                device_url=SHUTTER.device_url,
                exec_id="exec-1",
                new_state=ExecutionState.FAILED.value,
            )
        ]
    )
    await coordinator.async_refresh()

    assert len(events) == 1
    event_data = events[0].data
    assert event_data["exec_id"] == "exec-1"
    assert event_data["device_url"] == "unknown"
    assert event_data["command_name"] == "unknown"
    assert event_data["failure_type"] == "unknown"
