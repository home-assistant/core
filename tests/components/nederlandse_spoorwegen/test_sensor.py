"""Test the Nederlandse Spoorwegen sensor."""

from unittest.mock import AsyncMock

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nederlandse_spoorwegen.const import (
    CONF_FROM,
    CONF_ROUTES,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
    INTEGRATION_TITLE,
    SUBENTRY_TYPE_ROUTE,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PLATFORM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import API_KEY

from tests.common import MockConfigEntry, snapshot_platform


async def test_config_import(
    hass: HomeAssistant,
    mock_nsapi,
    mock_sensor_platform,
    mock_setup_entry: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test sensor initialization."""
    await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_API_KEY: API_KEY,
                    CONF_ROUTES: [
                        {
                            CONF_NAME: "Spoorwegen Nederlande Station",
                            CONF_FROM: "ASD",
                            CONF_TO: "RTD",
                            CONF_VIA: "HT",
                        }
                    ],
                }
            ]
        },
    )

    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    assert (HOMEASSISTANT_DOMAIN, "deprecated_yaml") in issue_registry.issues
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
async def test_sensor(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_sensor_platform,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor initialization."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
async def test_single_trip_sensor(
    hass: HomeAssistant,
    mock_single_trip_nsapi: AsyncMock,
    mock_sensor_platform,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor initialization."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
async def test_no_trips_sensor(
    hass: HomeAssistant,
    mock_no_trips_nsapi: AsyncMock,
    mock_sensor_platform,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor initialization."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_with_api_connection_error(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_sensor_platform,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor behavior when API connection fails."""
    # Make API calls fail from the start
    mock_nsapi.get_trips.side_effect = RequestsConnectionError("Connection failed")

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Sensors should not be created at all if initial API call fails
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 0


@pytest.mark.parametrize(
    ("time_input", "route_name", "description"),
    [
        (None, "Current time route", "No specific time - should use current time"),
        ("08:30", "Morning commute", "Time only - should use today's date with time"),
        ("08:30:45", "Early commute", "Time with seconds - should truncate seconds"),
    ],
)
async def test_sensor_with_custom_time_parsing(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_sensor_platform,
    time_input,
    route_name,
    description,
) -> None:
    """Test sensor with different time parsing scenarios."""
    # Create a config entry with a route that has the specified time
    config_entry = MockConfigEntry(
        title=INTEGRATION_TITLE,
        data={CONF_API_KEY: API_KEY},
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_NAME: route_name,
                    CONF_FROM: "Ams",
                    CONF_TO: "Rot",
                    CONF_VIA: "Ht",
                    CONF_TIME: time_input,
                },
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title=f"{route_name} Route",
                unique_id=None,
                subentry_id=f"test_route_{time_input or 'none'}".replace(":", "_")
                .replace("-", "_")
                .replace(" ", "_"),
            ),
        ],
    )

    await setup_integration(hass, config_entry)
    await hass.async_block_till_done()

    # Should create 13 sensors for the route with time parsing
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 13

    # Verify sensor was created successfully with time parsing
    state = sensor_states[0]
    assert state is not None
    assert state.state != "unavailable"
    assert state.attributes.get("attribution") == "Data provided by NS"

    # The sensor should have a friendly name based on the route name
    friendly_name = state.attributes.get("friendly_name", "").lower()
    assert (
        route_name.lower() in friendly_name
        or route_name.replace(" ", "_").lower() in state.entity_id
    )


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")  # Amsterdam time: 16:30
async def test_coordinator_time_based_fetch_logic(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_config_entry_coordinator_time_tests: MockConfigEntry,
) -> None:
    """Test coordinator time-based fetch logic through sensor behavior.

    This test validates the coordinator's _get_time_from_route logic by checking
    sensor states. The frozen time is 16:30 Amsterdam time (14:30 UTC).

    The mock_config_entry includes 5 routes:
    1. No time (None) - should always fetch and create sensor
    2. Time: 08:00 - outside ±30min window - should NOT fetch, no sensor data
    3. Time: 28:00 - malformed time - should fallback to fetch now
    4. Time: 16:45 - within ±30min window - should fetch and create sensor
    5. Time: 17:15 - outside ±30min window (45min away) - should NOT fetch
    """
    await setup_integration(hass, mock_config_entry_coordinator_time_tests)
    await hass.async_block_till_done()

    # Check API call count - should only fetch for 3 routes:
    # Route 1 (no time), Route 3 (malformed time), Route 4 (within window)
    # Routes 2 and 5 should NOT fetch (outside ±30min window)
    assert mock_nsapi.get_trips.call_count == 3, (
        f"Expected 3 API calls, got {mock_nsapi.get_trips.call_count}"
    )

    # Get all sensor states
    sensor_states = hass.states.async_all("sensor")
    sensor_entity_ids = [state.entity_id for state in sensor_states]

    # Route 1 (no time) - should have sensor
    route1_sensors = [s for s in sensor_entity_ids if "to_work" in s]
    assert len(route1_sensors) > 0, "Route 1 (no time) should have created sensor"

    # Route 3 (malformed time) - should have sensor (fallback to fetch now)
    route3_sensors = [s for s in sensor_entity_ids if "malformed_time" in s]
    assert len(route3_sensors) > 0, (
        "Route 3 (malformed time) should have created sensor"
    )

    # Route 4 (within window) - should have sensor
    route4_sensors = [s for s in sensor_entity_ids if "within_window" in s]
    assert len(route4_sensors) > 0, "Route 4 (within window) should have created sensor"

    # Verify sensors have valid data (not unavailable)
    for sensor_id in route1_sensors + route3_sensors + route4_sensors:
        state = hass.states.get(sensor_id)
        assert state is not None
        # Sensors should have valid state values
        assert state.state not in [None, ""]
