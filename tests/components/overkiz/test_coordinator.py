"""Tests for the Overkiz data update coordinator."""

from unittest.mock import Mock

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.exceptions import (
    InvalidEventListenerIdException,
    MaintenanceException,
    ServiceUnavailableException,
    TooManyConcurrentRequestsException,
    TooManyRequestsException,
)
import pytest

from homeassistant.components.overkiz.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration

from tests.common import async_fire_time_changed

TEMPERATURE_SENSOR = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#2",
    "sensor.maple_residence_garden_radiator_bathroom_temperature_sensor_temperature",
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
