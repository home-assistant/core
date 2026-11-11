"""Test the recorder database usage report."""

from datetime import UTC, datetime, timedelta
import threading
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_purge_done,
    async_wait_recording_done,
    do_adhoc_statistics,
)
from pytest_homeassistant.typing import (
    MockHAClientWebSocket,
    RecorderInstanceContextManager,
    WebSocketGenerator,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.database_usage import (
    CACHE_TIME,
    DATA_DATABASE_USAGE,
    REFRESH_INTERVAL,
    DatabaseUsage,
    _attribute_lengths,
    get_database_usage,
)
from homeassistant.components.recorder.db_schema import (
    ALL_TABLES,
    StateAttributes,
    States,
    Statistics,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
POWER_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "W",
}
BYTES_MATCHER = path_type({r".*bytes": (int,), "duration": (float,)}, regex=True)


async def _record_data(hass: HomeAssistant) -> None:
    """Record states and statistics."""
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    for value in range(10):
        hass.states.async_set("sensor.busy", str(value), POWER_ATTRIBUTES)
    hass.states.async_set("sensor.quiet", "1", {"unit_of_measurement": "W"})
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


async def _async_usage(client: MockHAClientWebSocket, **kwargs: Any) -> Any:
    """Return the database usage report from the websocket API."""
    await client.send_json_auto_id({"type": "recorder/database_usage", **kwargs})
    response = await client.receive_json()
    assert response["success"]
    return response["result"]


SPREAD = {
    "states": ("entities", "states_bytes"),
    "state_attributes": ("entities", "attributes_bytes"),
    "statistics": ("statistics", "statistics_bytes"),
    "statistics_short_term": ("statistics", "statistics_short_term_bytes"),
}


def _assert_spread(usage: DatabaseUsage, *tables: str) -> None:
    """Assert the bytes of tables with rows are spread over them, rounded per row."""
    assert usage["tables"] is not None
    table_bytes = {table["table"]: table["bytes"] for table in usage["tables"]}
    for table in tables:
        rows, key = SPREAD[table]
        assert sum(row[key] for row in usage[rows]) == pytest.approx(
            table_bytes[table], abs=len(usage[rows])
        )


def _by_id(rows: list[dict[str, Any]], key: str) -> dict[str | None, dict[str, Any]]:
    """Return report rows by id."""
    return {row[key]: row for row in rows}


async def test_database_usage(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the report lists the space entities and statistics use."""
    client = await hass_ws_client()
    freezer.move_to(START)
    await _record_data(hass)

    result = await _async_usage(client, refresh=True)

    assert {table["table"] for table in result["tables"]} >= set(ALL_TABLES)
    _assert_spread(result, *SPREAD)
    assert {
        "duration": result["duration"],
        "entities": sorted(result["entities"], key=lambda row: row["entity_id"]),
        "generated_at": result["generated_at"],
        "statistics": sorted(result["statistics"], key=lambda row: row["statistic_id"]),
    } == snapshot(matcher=BYTES_MATCHER)


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_database_usage_sqlite_size(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test SQLite reports every table, the file size and the free pages."""
    await _record_data(hass)
    for value in range(10):
        hass.states.async_set(f"sensor.big_{value}", "1", {"text": "a" * 15000})
    await async_wait_recording_done(hass)
    await recorder_mock.async_add_executor_job(_delete_states, recorder_mock)

    usage = await recorder_mock.async_add_executor_job(
        get_database_usage, recorder_mock
    )

    (
        page_size,
        page_count,
        free_pages,
        tables,
    ) = await recorder_mock.async_add_executor_job(_sqlite_pages, recorder_mock)
    assert usage["tables"] is not None
    assert {table["table"] for table in usage["tables"]} == tables
    assert usage["total_bytes"] == page_count * page_size
    assert usage["free_bytes"] == free_pages * page_size > 0
    # Only the pages of the schema table itself are left out
    assert (
        sum(table["bytes"] for table in usage["tables"]) + usage["free_bytes"]
        < usage["total_bytes"]
    )


def _sqlite_pages(instance: Recorder) -> tuple[int, int, int, set[str]]:
    """Return the page size, page count, free pages and tables of SQLite."""
    with session_scope(session=instance.get_session(), read_only=True) as session:
        return (
            session.execute(text("PRAGMA page_size")).scalar_one(),
            session.execute(text("PRAGMA page_count")).scalar_one(),
            session.execute(text("PRAGMA freelist_count")).scalar_one(),
            {
                name
                for (name,) in session.execute(
                    text("SELECT DISTINCT tbl_name FROM sqlite_master")
                )
            },
        )


def _delete_states(instance: Recorder) -> None:
    """Delete all states and attributes so their pages become free."""
    with session_scope(session=instance.get_session()) as session:
        session.query(States).delete()
        session.query(StateAttributes).delete()


@pytest.mark.skip_on_db_engine(["sqlite", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_database_usage_mysql_size(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test MySQL reports the tables and their free space as the size on disk."""
    await _record_data(hass)

    usage = await recorder_mock.async_add_executor_job(
        get_database_usage, recorder_mock
    )

    assert usage["tables"] is not None
    assert usage["free_bytes"] is not None
    assert usage["total_bytes"] == (
        sum(table["bytes"] for table in usage["tables"]) + usage["free_bytes"]
    )


@pytest.mark.skip_on_db_engine(["sqlite", "mysql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_database_usage_postgresql_size(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test PostgreSQL reports the database size and no free space."""
    await _record_data(hass)

    usage = await recorder_mock.async_add_executor_job(
        get_database_usage, recorder_mock
    )

    assert usage["tables"] is not None
    assert usage["free_bytes"] is None
    assert usage["total_bytes"] >= sum(table["bytes"] for table in usage["tables"])


@pytest.mark.usefixtures("recorder_mock")
async def test_database_usage_empty(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the report of a database without states or statistics."""
    client = await hass_ws_client()
    freezer.move_to(START)

    result = await _async_usage(client, refresh=True)

    assert result["total_bytes"] > 0
    assert result["entities"] == []
    assert result["statistics"] == []
    assert result["generated_at"] == START.isoformat()


def _add_unattributed_rows(instance: Recorder) -> None:
    """Add rows without a known owner, and attributes shared by two entities."""
    with session_scope(session=instance.get_session()) as session:
        shared_id = session.query(States.attributes_id).limit(1).scalar()
        metadata_ids = [
            metadata_id
            for (metadata_id,) in session.query(States.metadata_id).distinct()
        ]
        session.add_all(
            [
                StateAttributes(shared_attrs='{"orphan":true}', hash=1),
                States(state="no metadata", metadata_id=None),
                Statistics(metadata_id=None, start_ts=0.0, created_ts=0.0),
                *(
                    States(
                        state="shared",
                        metadata_id=metadata_id,
                        attributes_id=shared_id,
                    )
                    for metadata_id in metadata_ids
                ),
            ]
        )


async def test_database_usage_attribution(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test shared, orphaned and ownerless rows are each counted once."""
    hass.states.async_set("sensor.first", "1", {"shared": True})
    hass.states.async_set("sensor.second", "1", {"other": True})
    await async_wait_recording_done(hass)
    await recorder_mock.async_add_executor_job(_add_unattributed_rows, recorder_mock)

    usage = await recorder_mock.async_add_executor_job(
        get_database_usage, recorder_mock
    )

    _assert_spread(usage, "states", "state_attributes", "statistics")
    entities = _by_id(usage["entities"], "entity_id")
    assert {
        entity_id: (row["states"], row["attributes_bytes"] > 0)
        for entity_id, row in entities.items()
    } == {
        # Shared attributes are counted once, so the spread above adds up
        "sensor.first": (2, True),
        "sensor.second": (2, True),
        None: (1, True),
    }
    assert usage["statistics"] == [
        {
            "statistic_id": None,
            "source": None,
            "statistics": 1,
            "statistics_short_term": 0,
            "statistics_bytes": usage["statistics"][0]["statistics_bytes"],
            "statistics_short_term_bytes": 0,
        }
    ]


@pytest.mark.parametrize("repack", [False, True])
async def test_database_usage_after_purge(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    repack: bool,
) -> None:
    """Test the report only counts the rows a purge keeps."""
    client = await hass_ws_client()
    freezer.move_to(START)
    await _record_data(hass)
    freezer.move_to(START + timedelta(days=2))
    hass.states.async_set("sensor.busy", "new", {"after": "purge"})
    await async_wait_recording_done(hass)

    await hass.services.async_call(
        recorder.DOMAIN, "purge", {"keep_days": 1, "repack": repack}, blocking=True
    )
    await async_wait_purge_done(hass)
    result = await _async_usage(client, refresh=True)

    _assert_spread(result, "states", "state_attributes", "statistics")
    assert [
        (row["entity_id"], row["states"], row["attributes_bytes"] > 0)
        for row in result["entities"]
    ] == [("sensor.busy", 1, True)]


async def test_database_usage_weighting(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test states are spread per row and attributes by their size in bytes."""
    hass.states.async_set("sensor.large", "1", {"text": "é" * 2000})
    for value in range(9):
        hass.states.async_set("sensor.noisy", str(value), {"text": "a" * 500})
    await async_wait_recording_done(hass)

    usage = await recorder_mock.async_add_executor_job(
        get_database_usage, recorder_mock
    )

    _assert_spread(usage, "states", "state_attributes")
    entities = _by_id(usage["entities"], "entity_id")
    large, noisy = entities["sensor.large"], entities["sensor.noisy"]
    assert noisy["states_bytes"] == pytest.approx(9 * large["states_bytes"], abs=9)
    # JSON lengths in bytes; the noisy states share one attributes row
    assert large["attributes_bytes"] / noisy["attributes_bytes"] == pytest.approx(
        4011 / 511, rel=0.01
    )


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_database_usage_without_dbstat(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test SQLite without dbstat reports row counts without table sizes."""
    await _record_data(hass)

    with patch(
        "homeassistant.components.recorder.database_usage.SQLITE_DBSTAT_QUERY",
        "SELECT * FROM no_such_table",
    ):
        usage = await recorder_mock.async_add_executor_job(
            get_database_usage, recorder_mock
        )

    assert usage["tables"] is None
    assert usage["total_bytes"] > 0
    assert usage["free_bytes"] is not None
    assert {
        (row["entity_id"], row["states"], row["states_bytes"], row["attributes_bytes"])
        for row in usage["entities"]
    } == {("sensor.busy", 10, None, None), ("sensor.quiet", 1, None, None)}
    assert {
        (row["statistic_id"], row["statistics_bytes"]) for row in usage["statistics"]
    } == {("sensor.busy", None), ("test:external", None)}


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_database_usage_dbstat_error(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test other SQLite errors are not mistaken for a missing dbstat."""
    client = await hass_ws_client()

    with patch(
        "homeassistant.components.recorder.database_usage.SQLITE_DBSTAT_QUERY",
        "SELECT * FROM",
    ):
        await client.send_json_auto_id(
            {"type": "recorder/database_usage", "refresh": True}
        )
        response = await client.receive_json()

    assert not response["success"]


@pytest.mark.parametrize(
    ("elapsed", "runs"),
    [
        pytest.param(REFRESH_INTERVAL - timedelta(seconds=1), 1, id="too_soon"),
        pytest.param(REFRESH_INTERVAL, 2, id="refresh"),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_database_usage_refresh_interval(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    elapsed: timedelta,
    runs: int,
) -> None:
    """Test a refresh shortly after the last one returns that report."""
    client = await hass_ws_client()
    freezer.move_to(START)

    with patch(
        "homeassistant.components.recorder.database_usage.get_database_usage",
        wraps=get_database_usage,
    ) as mock_usage:
        await _async_usage(client, refresh=True)
        freezer.tick(elapsed)
        result = await _async_usage(client, refresh=True)

    assert mock_usage.call_count == runs
    assert result["generated_at"] == (START + elapsed * (runs - 1)).isoformat()


@pytest.mark.usefixtures("recorder_mock")
async def test_database_usage_cached(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a report is kept for an hour and never started without refresh."""
    client = await hass_ws_client()
    freezer.move_to(START)

    with patch(
        "homeassistant.components.recorder.database_usage.get_database_usage",
        wraps=get_database_usage,
    ) as mock_usage:
        assert await _async_usage(client) is None
        report = await _async_usage(client, refresh=True)
        freezer.tick(CACHE_TIME - timedelta(seconds=1))
        async_fire_time_changed(hass)
        assert await _async_usage(client) == report
        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        assert await _async_usage(client) is None

    assert mock_usage.call_count == 1


@pytest.mark.usefixtures("recorder_mock")
async def test_database_usage_slow_run(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a run is dated and kept from when it finished."""
    client = await hass_ws_client()
    freezer.move_to(START)
    slow = timedelta(minutes=10)

    def slow_attribute_lengths(*args: Any) -> dict[int | None, int]:
        freezer.tick(slow)
        return _attribute_lengths(*args)

    with patch(
        "homeassistant.components.recorder.database_usage._attribute_lengths",
        side_effect=slow_attribute_lengths,
    ):
        report = await _async_usage(client, refresh=True)

    assert report["generated_at"] == (START + slow).isoformat()
    assert report["duration"] == slow.total_seconds()
    freezer.tick(CACHE_TIME - timedelta(seconds=1))
    async_fire_time_changed(hass)
    assert await _async_usage(client) == report


async def test_database_usage_single_flight(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test a cancelled request leaves the run to the requests still waiting."""
    cache = hass.data[DATA_DATABASE_USAGE]
    release = threading.Event()

    def blocked_usage(instance: Recorder) -> DatabaseUsage:
        release.wait()
        return get_database_usage(instance)

    with patch(
        "homeassistant.components.recorder.database_usage.get_database_usage",
        side_effect=blocked_usage,
    ) as mock_usage:
        first = hass.async_create_task(cache.async_refresh(recorder_mock))
        second = hass.async_create_task(cache.async_refresh(recorder_mock))
        first.cancel()
        release.set()
        usage = await second

    assert first.cancelled()
    assert mock_usage.call_count == 1
    assert cache.usage is usage


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
        await client.send_json_auto_id(
            {"type": "recorder/database_usage", "refresh": True}
        )
        response = await client.receive_json()

    assert not response["success"]
    assert await _async_usage(client) is None
    assert (await _async_usage(client, refresh=True))["total_bytes"] > 0


async def test_database_usage_during_migration(
    recorder_mock: Recorder, hass_ws_client: WebSocketGenerator
) -> None:
    """Test a refresh is refused while the database is migrated."""
    client = await hass_ws_client()

    with patch.object(recorder_mock, "migration_in_progress", True):
        await client.send_json_auto_id(
            {"type": "recorder/database_usage", "refresh": True}
        )
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "migration_in_progress"


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


async def test_database_usage_waits_for_database_ready(
    async_test_recorder: RecorderInstanceContextManager,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a refresh during startup waits until the database is ready."""
    client = await hass_ws_client()
    recorder_helper.async_initialize_recorder(hass)

    async with async_test_recorder(
        hass, wait_recorder=False, wait_recorder_setup=False
    ):
        await client.send_json_auto_id(
            {"type": "recorder/database_usage", "refresh": True}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["total_bytes"] > 0


async def test_database_usage_recorder_failed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test an error is returned when the recorder failed to start."""
    client = await hass_ws_client()
    with patch("homeassistant.components.recorder.migration._migrate_schema"):
        recorder_helper.async_initialize_recorder(hass)
        assert not await async_setup_component(
            hass,
            recorder.DOMAIN,
            {
                recorder.DOMAIN: {
                    recorder.CONF_DB_URL: "sqlite:////no_dir/no_file.db",
                    recorder.CONF_DB_RETRY_WAIT: 0,
                }
            },
        )
    await hass.async_add_executor_job(recorder.get_instance(hass).join)

    await client.send_json_auto_id({"type": "recorder/database_usage", "refresh": True})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "recorder_not_ready"
