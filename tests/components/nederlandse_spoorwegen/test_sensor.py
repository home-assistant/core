"""Test the Nederlandse Spoorwegen sensor."""

from collections.abc import Generator
from datetime import date, datetime
from unittest.mock import AsyncMock, patch
import zoneinfo

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
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_PLATFORM,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import API_KEY

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def mock_sensor_platform() -> Generator:
    """Override PLATFORMS for NS integration."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.PLATFORMS",
        [Platform.SENSOR],
    ) as mock_platform:
        yield mock_platform


async def test_config_import(
    hass: HomeAssistant,
    mock_nsapi,
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
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor initialization."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_single_trip_sensor(
    hass: HomeAssistant,
    mock_single_trip_nsapi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor initialization."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_trips_sensor(
    hass: HomeAssistant,
    mock_no_trips_nsapi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor initialization."""
    await setup_integration(hass, mock_config_entry)

    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ):
        state = hass.states.get(entity_entry.entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN


async def test_sensor_with_api_connection_error(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
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
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_with_custom_time_parsing(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
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


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_with_time_filtering(
    hass: HomeAssistant,
    mock_nsapi: AsyncMock,
) -> None:
    """Test that the time-based window filter correctly filters trips.

    This test verifies that:
    1. Trips BEFORE the configured time are filtered out
    2. Trips AT or AFTER the configured time are included
    3. The filtering is based on time-only (ignoring date)
    """
    # Create a config entry with a route that has time set to 16:00
    # Test frozen at: 2025-09-15 14:30 UTC = 16:30 Amsterdam time
    # The fixture includes trips at the following times:
    # 16:24/16:25 (trip 0) - FILTERED OUT (departed before 16:30 now)
    # 16:34/16:35 (trip 1) - INCLUDED (>= 16:00 configured time AND > 16:30 now)
    # With time=16:00, only future trips at or after 16:00 are included
    config_entry = MockConfigEntry(
        title=INTEGRATION_TITLE,
        data={CONF_API_KEY: API_KEY},
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_NAME: "Afternoon commute",
                    CONF_FROM: "Ams",
                    CONF_TO: "Rot",
                    CONF_VIA: "Ht",
                    CONF_TIME: "16:00",
                },
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title="Afternoon Route",
                unique_id=None,
                subentry_id="test_route_time_filter",
            ),
        ],
    )

    await setup_integration(hass, config_entry)
    await hass.async_block_till_done()

    # Should create sensors for the route
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 13

    # Find the actual departure time sensor and next departure sensor
    actual_departure_sensor = hass.states.get("sensor.afternoon_commute_departure")
    next_departure_sensor = hass.states.get("sensor.afternoon_commute_next_departure")

    assert actual_departure_sensor is not None, "Actual departure sensor not found"
    assert actual_departure_sensor.state != STATE_UNKNOWN

    # The sensor state is a UTC timestamp, convert it to Amsterdam time
    ams_tz = zoneinfo.ZoneInfo("Europe/Amsterdam")

    departure_dt = datetime.fromisoformat(actual_departure_sensor.state)
    departure_local = departure_dt.astimezone(ams_tz)

    hour = departure_local.hour
    minute = departure_local.minute
    # Verify first trip: is NOT before 16:00 (i.e., filtered trips are excluded)
    assert hour >= 16, (
        f"Expected first trip at or after 16:00 Amsterdam time, but got {hour}:{minute:02d}. "
        "This means trips before the configured time were NOT filtered out by the time window filter."
    )

    # Verify next trip also passes the filter
    assert next_departure_sensor is not None, "Next departure sensor not found"
    next_departure_dt = datetime.fromisoformat(next_departure_sensor.state)
    next_departure_local = next_departure_dt.astimezone(ams_tz)

    next_hour = next_departure_local.hour
    next_minute = next_departure_local.minute

    # Verify next trip is also at or after 16:00
    assert next_hour >= 16, (
        f"Expected next trip at or after 16:00 Amsterdam time, but got {next_hour}:{next_minute:02d}. "
        "This means the window filter is not applied consistently to all trips."
    )

    # Verify next trip is after the first trip
    assert (next_hour, next_minute) > (hour, minute), (
        f"Expected next trip ({next_hour}:{next_minute:02d}) to be after first trip ({hour}:{minute:02d})"
    )


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_with_time_filtering_next_day(
    hass: HomeAssistant,
    mock_tomorrow_trips_nsapi: AsyncMock,
) -> None:
    """Test that time filtering automatically rolls over to next day when time is in past.

    This test verifies the day boundary logic:
    1. When configured time is >1 hour in the past, coordinator queries tomorrow's trips
    2. The API is called with tomorrow's date + configured time
    3. This ensures users get their morning commute trips even when configured in evening

    Example: It's 16:30 (4:30 PM), user configured 08:00 (8:00 AM) for morning commute.
    Instead of showing no trips (since 08:00 already passed today), we show tomorrow's 08:00 trips.
    """
    # Current time: 16:30 Amsterdam (14:30 UTC frozen)
    # Configured time: 08:00 (8.5 hours in the past, >1 hour threshold)
    # Expected behavior: Query tomorrow (2025-09-16) at 08:00
    config_entry = MockConfigEntry(
        title=INTEGRATION_TITLE,
        data={CONF_API_KEY: API_KEY},
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_NAME: "Morning commute",
                    CONF_FROM: "Ams",
                    CONF_TO: "Rot",
                    CONF_VIA: "Ht",
                    CONF_TIME: "08:00",
                },
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title="Morning Route",
                unique_id=None,
                subentry_id="test_route_morning",
            ),
        ],
    )

    await setup_integration(hass, config_entry)
    await hass.async_block_till_done()

    # Should create sensors for the route
    sensor_states = hass.states.async_all("sensor")
    assert len(sensor_states) == 13

    # Find the actual departure sensor
    actual_departure_sensor = hass.states.get("sensor.morning_commute_departure")

    assert actual_departure_sensor is not None, "Actual departure sensor not found"

    # The sensor should have a valid trip
    assert actual_departure_sensor.state != STATE_UNKNOWN, (
        "Expected to have trips from tomorrow when configured time is in the past"
    )

    # Verify the first trip is tomorrow morning at or after 08:00
    # The fixture has trips at 08:24, 08:34 on 2025-09-16 (tomorrow)
    departure_dt = datetime.fromisoformat(actual_departure_sensor.state)
    ams_tz = zoneinfo.ZoneInfo("Europe/Amsterdam")
    departure_local = departure_dt.astimezone(ams_tz)

    departure_hour = departure_local.hour
    departure_minute = departure_local.minute
    departure_date = departure_local.date()

    # Verify trip is at or after 08:00 morning time
    assert 8 <= departure_hour < 12, (
        f"Expected morning trip (08:00-11:59) but got {departure_hour}:{departure_minute:02d}. "
        "This means the rollover to tomorrow logic is not working correctly."
    )

    # Verify trip is from tomorrow (2025-09-16)
    expected_date = date(2025, 9, 16)
    assert departure_date == expected_date, (
        f"Expected trip from tomorrow (2025-09-16) but got {departure_date}. "
        "The coordinator should query tomorrow's trips when configured time is >1 hour in the past."
    )
