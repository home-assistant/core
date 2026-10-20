"""Tests for the GTFS sensor."""

from pathlib import Path
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pygtfs
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_yaml_sensor

DAY_ROUTE = {"origin": "S1", "destination": "S3"}
NIGHT_ROUTE = {"origin": "N1", "destination": "N2"}
DAY_ENTITY_ID = "sensor.test_agency_s1_to_s3_next_departure"
NIGHT_ENTITY_ID = "sensor.test_agency_n1_to_n2_next_departure"
SECOND_ENTITY_ID = "sensor.test_agency_s2_to_s3_next_departure"
NO_DEPARTURE_ENTITY_ID = "sensor.gtfs_sensor"


def _import_feed(feed_file: Path) -> None:
    schedule = pygtfs.Schedule(str(feed_file.with_suffix(".sqlite")))
    pygtfs.append_feed(schedule, str(feed_file))
    schedule.session.close()
    schedule.engine.dispose()


def _feed_count(feed_file: Path) -> int:
    schedule = pygtfs.Schedule(str(feed_file.with_suffix(".sqlite")))
    count = len(schedule.feeds)
    schedule.session.close()
    schedule.engine.dispose()
    return count


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("feed_file")
async def test_sensor(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the sensor state and attributes."""
    await setup_yaml_sensor(hass, **DAY_ROUTE)

    assert hass.states.get(DAY_ENTITY_ID) == snapshot


@pytest.mark.parametrize(
    ("now", "config", "entity_id", "state", "attributes"),
    [
        pytest.param(
            "2026-10-19 07:30:00-04:00",
            DAY_ROUTE,
            DAY_ENTITY_ID,
            "2026-10-19T12:00:00+00:00",
            {"day": "today", "first": True, "last": False},
            id="first_departure",
        ),
        pytest.param(
            "2026-10-19 09:00:00-04:00",
            DAY_ROUTE,
            DAY_ENTITY_ID,
            "2026-10-19T21:00:00+00:00",
            {"day": "today", "first": False, "last": True},
            id="last_departure",
        ),
        pytest.param(
            "2026-10-19 18:00:00-04:00",
            DAY_ROUTE,
            NO_DEPARTURE_ENTITY_ID,
            STATE_UNKNOWN,
            {"info": "No more departures today"},
            id="no_more_departures",
        ),
        pytest.param(
            "2026-10-20 00:15:00-04:00",
            DAY_ROUTE,
            DAY_ENTITY_ID,
            "2026-10-20T12:00:00+00:00",
            {"day": "today", "first": True},
            id="after_midnight",
        ),
        pytest.param(
            "2026-10-19 07:30:00-04:00",
            {**DAY_ROUTE, "offset": "00:45:00"},
            DAY_ENTITY_ID,
            "2026-10-19T21:00:00+00:00",
            {"offset": 45.0},
            id="offset",
        ),
        pytest.param(
            "2026-10-19 07:30:00-04:00",
            {**DAY_ROUTE, "name": "Commute"},
            "sensor.commute",
            "2026-10-19T12:00:00+00:00",
            {"friendly_name": "Commute"},
            id="custom_name",
        ),
        pytest.param(
            "2026-10-19 07:30:00-04:00",
            {**DAY_ROUTE, "include_tomorrow": True},
            DAY_ENTITY_ID,
            "2026-10-19T12:00:00+00:00",
            {"day": "today"},
            id="include_tomorrow_before_last",
        ),
        pytest.param(
            "2026-10-19 18:00:00-04:00",
            {**DAY_ROUTE, "include_tomorrow": True},
            DAY_ENTITY_ID,
            "2026-10-20T12:00:00+00:00",
            {
                "day": "tomorrow",
                "first": True,
                "arrival": "2026-10-20T12:20:00+00:00",
            },
            id="include_tomorrow_after_last",
        ),
        pytest.param(
            "2026-10-20 00:15:00-04:00",
            NIGHT_ROUTE,
            NIGHT_ENTITY_ID,
            "2026-10-20T04:30:00+00:00",
            {"arrival": "2026-10-20T04:50:00+00:00"},
            id="overnight_trip",
        ),
        pytest.param(
            "2026-10-20 00:40:00-04:00",
            NIGHT_ROUTE,
            NO_DEPARTURE_ENTITY_ID,
            STATE_UNKNOWN,
            {"info": "No more departures today"},
            id="overnight_trip_departed",
        ),
    ],
)
@pytest.mark.usefixtures("feed_file")
async def test_next_departure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    now: str,
    config: dict[str, Any],
    entity_id: str,
    state: str,
    attributes: dict[str, Any],
) -> None:
    """Test the next departure for a route at a point in time."""
    freezer.move_to(now)
    await setup_yaml_sensor(hass, **config)

    assert (sensor := hass.states.get(entity_id)) is not None
    assert sensor.state == state
    assert {key: sensor.attributes[key] for key in attributes} == attributes


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("feed_file")
async def test_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, snapshot: SnapshotAssertion
) -> None:
    """Test polling through departures, to none, and back."""
    await setup_yaml_sensor(hass, **DAY_ROUTE)
    assert hass.states.get(DAY_ENTITY_ID) == snapshot(name="first_departure")

    freezer.move_to("2026-10-19 09:00:00-04:00")
    async_fire_time_changed(hass)
    # Entity polling runs as a background task.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(DAY_ENTITY_ID) == snapshot(name="last_departure")

    freezer.move_to("2026-10-19 18:00:00-04:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(DAY_ENTITY_ID) == snapshot(name="no_departures")

    freezer.move_to("2026-10-20 00:15:00-04:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(DAY_ENTITY_ID) == snapshot(name="next_day")


async def test_missing_data_file(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test no sensor is created when the feed file is absent from the config dir."""
    await setup_yaml_sensor(hass, **DAY_ROUTE)

    assert not hass.states.async_all(SENSOR_DOMAIN)
    assert "The given GTFS data file/folder was not found" in caplog.text


@pytest.mark.parametrize(
    ("config", "message"),
    [
        pytest.param(
            {"origin": "S9", "destination": "S3"},
            "Origin stop ID S9 not found",
            id="origin",
        ),
        pytest.param(
            {"origin": "S1", "destination": "S9"},
            "Destination stop ID S9 not found",
            id="destination",
        ),
    ],
)
@pytest.mark.usefixtures("feed_file")
async def test_unknown_stop(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config: dict[str, Any],
    message: str,
) -> None:
    """Test a stop missing from the feed makes the sensor unavailable."""
    await setup_yaml_sensor(hass, **config)

    assert (state := hass.states.get("sensor.unnamed_device")) is not None
    assert state.state == STATE_UNAVAILABLE
    assert message in caplog.text


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
async def test_existing_database_is_reused(
    hass: HomeAssistant, feed_file: Path
) -> None:
    """Test an already imported database is opened without re-importing."""
    await hass.async_add_executor_job(_import_feed, feed_file)
    await setup_yaml_sensor(hass, **DAY_ROUTE)

    assert (state := hass.states.get(DAY_ENTITY_ID)) is not None
    assert state.state == "2026-10-19T12:00:00+00:00"
    assert await hass.async_add_executor_job(_feed_count, feed_file) == 1


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
async def test_sensors_sharing_a_feed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, feed_file: Path
) -> None:
    """Test two sensors reading one feed update independently."""
    # Importing first avoids the legacy table-creation race between sensors.
    await hass.async_add_executor_job(_import_feed, feed_file)
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: [
                {"platform": "gtfs", "data": "feed.zip", **DAY_ROUTE},
                {
                    "platform": "gtfs",
                    "data": "feed.zip",
                    "origin": "S2",
                    "destination": "S3",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert (state := hass.states.get(DAY_ENTITY_ID)) is not None
    assert state.state == "2026-10-19T12:00:00+00:00"
    assert (state := hass.states.get(SECOND_ENTITY_ID)) is not None
    assert state.state == "2026-10-19T12:10:00+00:00"

    freezer.move_to("2026-10-19 09:00:00-04:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (state := hass.states.get(DAY_ENTITY_ID)) is not None
    assert state.state == "2026-10-19T21:00:00+00:00"
    assert (state := hass.states.get(SECOND_ENTITY_ID)) is not None
    assert state.state == "2026-10-19T21:10:00+00:00"
