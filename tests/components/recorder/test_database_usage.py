"""Test the recorder database usage report."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
    do_adhoc_statistics,
)
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator
from sqlalchemy.exc import SQLAlchemyError
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.database_usage import (
    DATA_DATABASE_USAGE,
    get_database_usage,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
POWER_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "W",
}
USAGE_TABLES = {
    "event_data",
    "events",
    "state_attributes",
    "states",
    "statistics",
    "statistics_short_term",
}
BYTES_MATCHER = path_type({r".*bytes": (int,)}, regex=True)


async def _record_data(hass: HomeAssistant) -> None:
    """Record states, statistics and an event."""
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    for value in range(10):
        hass.states.async_set("sensor.busy", str(value), POWER_ATTRIBUTES)
    hass.states.async_set("sensor.quiet", "1", {"unit_of_measurement": "W"})
    hass.bus.async_fire("my_event", {"some": "data"})
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=START)
    hourly = [
        {"start": START + timedelta(hours=hour), "mean": 1.0} for hour in range(3)
    ]
    async_import_statistics(
        hass,
        {
            "has_sum": False,
            "mean_type": 1,
            "name": None,
            "source": "recorder",
            "statistic_id": "sensor.busy",
            "unit_class": "power",
            "unit_of_measurement": "W",
        },
        hourly,
    )
    async_add_external_statistics(
        hass,
        {
            "has_sum": False,
            "mean_type": 1,
            "name": "External",
            "source": "test",
            "statistic_id": "test:external",
            "unit_class": "power",
            "unit_of_measurement": "W",
        },
        hourly[:1],
    )
    await async_wait_recording_done(hass)


async def _async_usage(client: MockHAClientWebSocket, **kwargs: Any) -> dict[str, Any]:
    """Return the database usage report from the websocket API."""
    await client.send_json_auto_id({"type": "recorder/database_usage", **kwargs})
    response = await client.receive_json()
    assert response["success"]
    return response["result"]


async def test_database_usage(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the report lists entities and event types by the space they use."""
    client = await hass_ws_client()
    freezer.move_to(START)
    await _record_data(hass)

    result = await _async_usage(client)

    tables = {table["table"]: table["bytes"] for table in result["tables"]}
    assert tables.keys() >= USAGE_TABLES
    assert result["total_bytes"] >= sum(tables.values())
    # Each table's bytes are spread over the entities and event types using it
    assert sum(usage["bytes"] for usage in result["entities"]) + sum(
        usage["bytes"] for usage in result["event_types"]
    ) == pytest.approx(
        sum(tables[table] for table in USAGE_TABLES),
        abs=len(result["entities"]) + len(result["event_types"]),
    )
    # Startup events depend on the test harness, only my_event is snapshotted
    assert {
        "entities": result["entities"],
        "event_types": [
            usage
            for usage in result["event_types"]
            if usage["event_type"] == "my_event"
        ],
        "generated_at": result["generated_at"],
    } == snapshot(matcher=BYTES_MATCHER)


@pytest.mark.usefixtures("recorder_mock")
async def test_database_usage_empty(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the report of a database without states or statistics."""
    client = await hass_ws_client()
    freezer.move_to(START)

    result = await _async_usage(client)

    assert result["total_bytes"] > 0
    assert result["entities"] == []
    assert result["generated_at"] == START.isoformat()


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_database_usage_without_dbstat(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test SQLite table sizes are estimated when dbstat is missing."""
    await _record_data(hass)

    with patch(
        "homeassistant.components.recorder.database_usage.SQLITE_DBSTAT_QUERY",
        "SELECT * FROM no_such_table",
    ):
        usage = await recorder_mock.async_add_executor_job(
            get_database_usage, recorder_mock
        )

    assert {table["table"] for table in usage["tables"]} == USAGE_TABLES
    assert sum(table["bytes"] for table in usage["tables"]) <= usage["total_bytes"]
    assert usage["entities"][0]["entity_id"] == "sensor.busy"
    assert usage["entities"][0]["bytes"] > usage["entities"][1]["bytes"] > 0


@pytest.mark.parametrize(
    ("request_kwargs", "elapsed", "runs"),
    [
        pytest.param({}, timedelta(minutes=4), 1, id="cached"),
        pytest.param({"refresh": True}, timedelta(minutes=4), 2, id="refresh"),
        pytest.param({}, timedelta(minutes=5), 2, id="expired"),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_database_usage_cache(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    request_kwargs: dict[str, Any],
    elapsed: timedelta,
    runs: int,
) -> None:
    """Test a report is reused for five minutes unless a refresh is requested."""
    client = await hass_ws_client()
    freezer.move_to(START)

    with patch(
        "homeassistant.components.recorder.database_usage.get_database_usage",
        wraps=get_database_usage,
    ) as mock_usage:
        await _async_usage(client)
        freezer.tick(elapsed)
        result = await _async_usage(client, **request_kwargs)

    assert mock_usage.call_count == runs
    assert result["generated_at"] == (START + elapsed * (runs - 1)).isoformat()


async def test_database_usage_single_flight(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test concurrent requests, refresh included, wait for the same run."""
    cache = hass.data[DATA_DATABASE_USAGE]

    with patch(
        "homeassistant.components.recorder.database_usage.get_database_usage",
        wraps=get_database_usage,
    ) as mock_usage:
        first, second = await asyncio.gather(
            cache.async_get(recorder_mock, False),
            cache.async_get(recorder_mock, True),
        )

    assert mock_usage.call_count == 1
    assert first is second


@pytest.mark.usefixtures("recorder_mock")
async def test_database_usage_error_not_cached(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a failed run is not cached and the next request runs again."""
    client = await hass_ws_client()

    with patch(
        "homeassistant.components.recorder.database_usage.get_database_usage",
        side_effect=SQLAlchemyError,
    ):
        await client.send_json_auto_id({"type": "recorder/database_usage"})
        response = await client.receive_json()

    assert not response["success"]
    assert (await _async_usage(client))["total_bytes"] > 0


@pytest.mark.usefixtures("recorder_mock")
async def test_database_usage_requires_admin(
    hass_ws_client: WebSocketGenerator, hass_read_only_access_token: str
) -> None:
    """Test a non-admin user cannot read the report."""
    client = await hass_ws_client(access_token=hass_read_only_access_token)
    await client.send_json_auto_id({"type": "recorder/database_usage"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
