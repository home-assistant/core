"""Test util methods."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import lambda_stmt, text
from sqlalchemy.engine.result import ChunkedIteratorResult
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.lambdas import StatementLambdaElement

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder, util
from homeassistant.components.recorder.const import (
    DOMAIN,
    SQLITE_URL_PREFIX,
    SupportedDialect,
)
from homeassistant.components.recorder.db_schema import RecorderRuns
from homeassistant.components.recorder.history.modern import (
    _get_single_entity_start_time_stmt,
)
from homeassistant.components.recorder.models import (
    UnsupportedDialect,
    process_timestamp,
)
from homeassistant.components.recorder.util import (
    MIN_VERSION_SQLITE,
    RETRYABLE_MYSQL_ERRORS,
    UPCOMING_MIN_VERSION_SQLITE,
    database_job_retry_wrapper,
    end_incomplete_runs,
    is_second_sunday,
    resolve_period,
    retryable_database_job,
    retryable_database_job_method,
    session_scope,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .common import (
    async_wait_recording_done,
    corrupt_db_file,
    run_information_with_session,
)

from tests.common import async_test_home_assistant
from tests.typing import RecorderInstanceGenerator


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceGenerator,
) -> None:
    """Set up recorder."""


@pytest.fixture
def setup_recorder(recorder_mock: Recorder) -> None:
    """Set up recorder."""


async def test_session_scope_not_setup(
    hass: HomeAssistant,
    setup_recorder: None,
) -> None:
    """Try to create a session scope when not setup."""
    with (
        patch.object(util.get_instance(hass), "get_session", return_value=None),
        pytest.raises(RuntimeError),
        util.session_scope(hass=hass),
    ):
        pass


async def test_recorder_bad_execute(hass: HomeAssistant, setup_recorder: None) -> None:
    """Bad execute, retry 3 times."""

    def to_native(validate_entity_id=True):
        """Raise exception."""
        raise SQLAlchemyError

    mck1 = MagicMock()
    mck1.to_native = to_native

    with (
        pytest.raises(SQLAlchemyError),
        patch("homeassistant.components.recorder.core.time.sleep") as e_mock,
    ):
        util.execute((mck1,), to_native=True)

    assert e_mock.call_count == 2


def test_validate_or_move_away_sqlite_database(
    hass: HomeAssistant, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure a malformed sqlite database is moved away."""
    test_dir = tmp_path.joinpath("test_validate_or_move_away_sqlite_database")
    test_dir.mkdir()
    test_db_file = f"{test_dir}/broken.db"
    dburl = f"{SQLITE_URL_PREFIX}{test_db_file}"

    assert util.validate_sqlite_database(test_db_file) is False
    assert os.path.exists(test_db_file) is True
    assert util.validate_or_move_away_sqlite_database(dburl) is False

    corrupt_db_file(test_db_file)

    assert util.validate_sqlite_database(dburl) is False

    assert util.validate_or_move_away_sqlite_database(dburl) is False

    assert "corrupt or malformed" in caplog.text

    assert util.validate_sqlite_database(dburl) is False

    assert util.validate_or_move_away_sqlite_database(dburl) is True


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
async def test_last_run_was_recently_clean(
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test we can check if the last recorder run was recently clean.

    This is only implemented for SQLite.
    """
    config = {
        recorder.CONF_COMMIT_INTERVAL: 1,
    }
    async with async_test_home_assistant() as hass:
        return_values = []
        real_last_run_was_recently_clean = util.last_run_was_recently_clean

        def _last_run_was_recently_clean(cursor):
            return_values.append(real_last_run_was_recently_clean(cursor))
            return return_values[-1]

        # Test last_run_was_recently_clean is not called on new DB
        with patch(
            "homeassistant.components.recorder.util.last_run_was_recently_clean",
            wraps=_last_run_was_recently_clean,
        ) as last_run_was_recently_clean_mock:
            await async_setup_recorder_instance(hass, config)
            await hass.async_block_till_done()
            last_run_was_recently_clean_mock.assert_not_called()

        # Restart HA, last_run_was_recently_clean should return True
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        await hass.async_stop()

    async with async_test_home_assistant() as hass:
        with patch(
            "homeassistant.components.recorder.util.last_run_was_recently_clean",
            wraps=_last_run_was_recently_clean,
        ) as last_run_was_recently_clean_mock:
            await async_setup_recorder_instance(hass, config)
            last_run_was_recently_clean_mock.assert_called_once()
            assert return_values[-1] is True

        # Restart HA with a long downtime, last_run_was_recently_clean should return False
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        await hass.async_stop()

    thirty_min_future_time = dt_util.utcnow() + timedelta(minutes=30)

    async with async_test_home_assistant() as hass:
        with (
            patch(
                "homeassistant.components.recorder.util.last_run_was_recently_clean",
                wraps=_last_run_was_recently_clean,
            ) as last_run_was_recently_clean_mock,
            patch(
                "homeassistant.components.recorder.core.dt_util.utcnow",
                return_value=thirty_min_future_time,
            ),
        ):
            await async_setup_recorder_instance(hass, config)
            last_run_was_recently_clean_mock.assert_called_once()
            assert return_values[-1] is False

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        await hass.async_stop()


@pytest.mark.parametrize(
    "mysql_version",
    ["10.3.0-MariaDB", "8.0.0"],
)
def test_setup_connection_for_dialect_mysql(mysql_version) -> None:
    """Test setting up the connection for a mysql dialect."""
    instance_mock = MagicMock()
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT VERSION()":
            return [[mysql_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    util.setup_connection_for_dialect(instance_mock, "mysql", dbapi_connection, True)

    assert len(execute_args) == 3
    assert execute_args[0] == "SET session wait_timeout=28800"
    assert execute_args[1] == "SELECT VERSION()"
    assert execute_args[2] == "SET time_zone = '+00:00'"


@pytest.mark.parametrize(
    "sqlite_version",
    [str(UPCOMING_MIN_VERSION_SQLITE)],
)
def test_setup_connection_for_dialect_sqlite(sqlite_version: str) -> None:
    """Test setting up the connection for a sqlite dialect."""
    instance_mock = MagicMock()
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT sqlite_version()":
            return [[sqlite_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    assert (
        util.setup_connection_for_dialect(
            instance_mock, "sqlite", dbapi_connection, True
        )
        is not None
    )

    assert len(execute_args) == 5
    assert execute_args[0] == "PRAGMA journal_mode=WAL"
    assert execute_args[1] == "SELECT sqlite_version()"
    assert execute_args[2] == "PRAGMA cache_size = -16384"
    assert execute_args[3] == "PRAGMA synchronous=NORMAL"
    assert execute_args[4] == "PRAGMA foreign_keys=ON"

    execute_args = []
    assert (
        util.setup_connection_for_dialect(
            instance_mock, "sqlite", dbapi_connection, False
        )
        is None
    )

    assert len(execute_args) == 3
    assert execute_args[0] == "PRAGMA cache_size = -16384"
    assert execute_args[1] == "PRAGMA synchronous=NORMAL"
    assert execute_args[2] == "PRAGMA foreign_keys=ON"


@pytest.mark.parametrize(
    "sqlite_version",
    [str(UPCOMING_MIN_VERSION_SQLITE)],
)
def test_setup_connection_for_dialect_sqlite_zero_commit_interval(
    sqlite_version: str,
) -> None:
    """Test setting up the connection for a sqlite dialect with a zero commit interval."""
    instance_mock = MagicMock(commit_interval=0)
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT sqlite_version()":
            return [[sqlite_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    assert (
        util.setup_connection_for_dialect(
            instance_mock, "sqlite", dbapi_connection, True
        )
        is not None
    )

    assert len(execute_args) == 5
    assert execute_args[0] == "PRAGMA journal_mode=WAL"
    assert execute_args[1] == "SELECT sqlite_version()"
    assert execute_args[2] == "PRAGMA cache_size = -16384"
    assert execute_args[3] == "PRAGMA synchronous=FULL"
    assert execute_args[4] == "PRAGMA foreign_keys=ON"

    execute_args = []
    assert (
        util.setup_connection_for_dialect(
            instance_mock, "sqlite", dbapi_connection, False
        )
        is None
    )

    assert len(execute_args) == 3
    assert execute_args[0] == "PRAGMA cache_size = -16384"
    assert execute_args[1] == "PRAGMA synchronous=FULL"
    assert execute_args[2] == "PRAGMA foreign_keys=ON"


@pytest.mark.parametrize(
    ("mysql_version", "message"),
    [
        (
            "10.2.0-MariaDB",
            "Version 10.2.0 of MariaDB is not supported; minimum supported version is 10.3.0.",
        ),
        (
            "5.7.26-0ubuntu0.18.04.1",
            "Version 5.7.26 of MySQL is not supported; minimum supported version is 8.0.0.",
        ),
        (
            "some_random_response",
            "Version some_random_response of MySQL is not supported; minimum supported version is 8.0.0.",
        ),
    ],
)
def test_fail_outdated_mysql(
    caplog: pytest.LogCaptureFixture, mysql_version, message
) -> None:
    """Test setting up the connection for an outdated mysql version."""
    instance_mock = MagicMock()
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT VERSION()":
            return [[mysql_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    with pytest.raises(UnsupportedDialect):
        util.setup_connection_for_dialect(
            instance_mock, "mysql", dbapi_connection, True
        )

    assert message in caplog.text


@pytest.mark.parametrize(
    "mysql_version",
    [
        ("10.3.0"),
        ("8.0.0"),
    ],
)
def test_supported_mysql(caplog: pytest.LogCaptureFixture, mysql_version) -> None:
    """Test setting up the connection for a supported mysql version."""
    instance_mock = MagicMock()
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT VERSION()":
            return [[mysql_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    util.setup_connection_for_dialect(instance_mock, "mysql", dbapi_connection, True)

    assert "minimum supported version" not in caplog.text


@pytest.mark.parametrize(
    ("pgsql_version", "message"),
    [
        (
            "11.12 (Debian 11.12-1.pgdg100+1)",
            "Version 11.12 of PostgreSQL is not supported; minimum supported version is 12.0.",
        ),
        (
            "9.2.10",
            "Version 9.2.10 of PostgreSQL is not supported; minimum supported version is 12.0.",
        ),
        (
            "unexpected",
            "Version unexpected of PostgreSQL is not supported; minimum supported version is 12.0.",
        ),
    ],
)
def test_fail_outdated_pgsql(
    caplog: pytest.LogCaptureFixture, pgsql_version, message
) -> None:
    """Test setting up the connection for an outdated PostgreSQL version."""
    instance_mock = MagicMock()
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SHOW server_version":
            return [[pgsql_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    with pytest.raises(UnsupportedDialect):
        util.setup_connection_for_dialect(
            instance_mock, "postgresql", dbapi_connection, True
        )

    assert message in caplog.text


@pytest.mark.parametrize(
    "pgsql_version",
    ["14.0 (Debian 14.0-1.pgdg110+1)"],
)
def test_supported_pgsql(caplog: pytest.LogCaptureFixture, pgsql_version) -> None:
    """Test setting up the connection for a supported PostgreSQL version."""
    instance_mock = MagicMock()
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SHOW server_version":
            return [[pgsql_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    database_engine = util.setup_connection_for_dialect(
        instance_mock, "postgresql", dbapi_connection, True
    )

    assert "minimum supported version" not in caplog.text
    assert database_engine is not None
    assert database_engine.optimizer.slow_range_in_select is False


@pytest.mark.parametrize(
    ("sqlite_version", "message"),
    [
        (
            "3.30.0",
            "Version 3.30.0 of SQLite is not supported; minimum supported version is 3.31.0.",
        ),
        (
            "2.0.0",
            "Version 2.0.0 of SQLite is not supported; minimum supported version is 3.31.0.",
        ),
    ],
)
def test_fail_outdated_sqlite(
    caplog: pytest.LogCaptureFixture, sqlite_version, message
) -> None:
    """Test setting up the connection for an outdated sqlite version."""
    instance_mock = MagicMock()
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT sqlite_version()":
            return [[sqlite_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    with pytest.raises(UnsupportedDialect):
        util.setup_connection_for_dialect(
            instance_mock, "sqlite", dbapi_connection, True
        )

    assert message in caplog.text


@pytest.mark.parametrize(
    "sqlite_version",
    [
        ("3.31.0"),
        ("3.33.0"),
    ],
)
def test_supported_sqlite(caplog: pytest.LogCaptureFixture, sqlite_version) -> None:
    """Test setting up the connection for a supported sqlite version."""
    instance_mock = MagicMock()
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT sqlite_version()":
            return [[sqlite_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    database_engine = util.setup_connection_for_dialect(
        instance_mock, "sqlite", dbapi_connection, True
    )

    assert "minimum supported version" not in caplog.text
    assert database_engine is not None
    assert database_engine.optimizer.slow_range_in_select is False


@pytest.mark.parametrize(
    ("dialect", "message"),
    [
        ("mssql", "Database mssql is not supported"),
        ("oracle", "Database oracle is not supported"),
        ("some_db", "Database some_db is not supported"),
    ],
)
def test_warn_unsupported_dialect(
    caplog: pytest.LogCaptureFixture, dialect, message
) -> None:
    """Test setting up the connection for an outdated sqlite version."""
    instance_mock = MagicMock()
    dbapi_connection = MagicMock()

    with pytest.raises(UnsupportedDialect):
        util.setup_connection_for_dialect(
            instance_mock, dialect, dbapi_connection, True
        )

    assert message in caplog.text


@pytest.mark.parametrize(
    ("mysql_version", "min_version"),
    [
        (
            "10.5.16-MariaDB",
            "10.5.17",
        ),
        (
            "10.6.8-MariaDB",
            "10.6.9",
        ),
        (
            "10.7.1-MariaDB",
            "10.7.5",
        ),
        (
            "10.8.0-MariaDB",
            "10.8.4",
        ),
    ],
)
async def test_issue_for_mariadb_with_MDEV_25020(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mysql_version,
    min_version,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we create an issue for MariaDB versions affected.

    See https://jira.mariadb.org/browse/MDEV-25020.
    """
    instance_mock = MagicMock()
    instance_mock.hass = hass
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT VERSION()":
            return [[mysql_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    database_engine = await hass.async_add_executor_job(
        util.setup_connection_for_dialect,
        instance_mock,
        "mysql",
        dbapi_connection,
        True,
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "maria_db_range_index_regression")
    assert issue is not None
    assert issue.translation_placeholders == {"min_version": min_version}

    assert database_engine is not None
    assert database_engine.optimizer.slow_range_in_select is True


@pytest.mark.parametrize(
    "mysql_version",
    [
        "10.5.17-MariaDB",
        "10.6.9-MariaDB",
        "10.7.5-MariaDB",
        "10.8.4-MariaDB",
        "10.9.1-MariaDB",
    ],
)
async def test_no_issue_for_mariadb_with_MDEV_25020(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mysql_version,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we do not create an issue for MariaDB versions not affected.

    See https://jira.mariadb.org/browse/MDEV-25020.
    """
    instance_mock = MagicMock()
    instance_mock.hass = hass
    execute_args = []
    close_mock = MagicMock()

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT VERSION()":
            return [[mysql_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    database_engine = await hass.async_add_executor_job(
        util.setup_connection_for_dialect,
        instance_mock,
        "mysql",
        dbapi_connection,
        True,
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "maria_db_range_index_regression")
    assert issue is None

    assert database_engine is not None
    assert database_engine.optimizer.slow_range_in_select is False


async def test_issue_for_old_sqlite(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we create and delete an issue for old sqlite versions."""
    instance_mock = MagicMock()
    instance_mock.hass = hass
    execute_args = []
    close_mock = MagicMock()
    min_version = str(MIN_VERSION_SQLITE)

    def execute_mock(statement):
        nonlocal execute_args
        execute_args.append(statement)

    def fetchall_mock():
        nonlocal execute_args
        if execute_args[-1] == "SELECT sqlite_version()":
            return [[min_version]]
        return None

    def _make_cursor_mock(*_):
        return MagicMock(execute=execute_mock, close=close_mock, fetchall=fetchall_mock)

    dbapi_connection = MagicMock(cursor=_make_cursor_mock)

    database_engine = await hass.async_add_executor_job(
        util.setup_connection_for_dialect,
        instance_mock,
        "sqlite",
        dbapi_connection,
        True,
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "sqlite_too_old")
    assert issue is not None
    assert issue.translation_placeholders == {
        "min_version": str(UPCOMING_MIN_VERSION_SQLITE),
        "server_version": min_version,
    }

    min_version = str(UPCOMING_MIN_VERSION_SQLITE)
    database_engine = await hass.async_add_executor_job(
        util.setup_connection_for_dialect,
        instance_mock,
        "sqlite",
        dbapi_connection,
        True,
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "sqlite_too_old")
    assert issue is None
    assert database_engine is not None


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_basic_sanity_check(
    hass: HomeAssistant, setup_recorder: None, recorder_db_url: str
) -> None:
    """Test the basic sanity checks with a missing table.

    This test is specific for SQLite.
    """
    cursor = util.get_instance(hass).engine.raw_connection().cursor()

    assert util.basic_sanity_check(cursor) is True

    cursor.execute("DROP TABLE states;")

    with pytest.raises(sqlite3.DatabaseError):
        util.basic_sanity_check(cursor)


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_combined_checks(
    hass: HomeAssistant,
    setup_recorder: None,
    caplog: pytest.LogCaptureFixture,
    recorder_db_url: str,
) -> None:
    """Run Checks on the open database.

    This test is specific for SQLite.
    """
    instance = util.get_instance(hass)
    instance.db_retry_wait = 0

    cursor = instance.engine.raw_connection().cursor()

    assert util.run_checks_on_open_db("fake_db_path", cursor) is None
    assert "could not validate that the sqlite3 database" in caplog.text

    caplog.clear()

    # We are patching recorder.util here in order
    # to avoid creating the full database on disk
    with patch(
        "homeassistant.components.recorder.util.basic_sanity_check", return_value=False
    ):
        caplog.clear()
        assert util.run_checks_on_open_db("fake_db_path", cursor) is None
        assert "could not validate that the sqlite3 database" in caplog.text

    # We are patching recorder.util here in order
    # to avoid creating the full database on disk
    with patch("homeassistant.components.recorder.util.last_run_was_recently_clean"):
        caplog.clear()
        assert util.run_checks_on_open_db("fake_db_path", cursor) is None
        assert "restarted cleanly and passed the basic sanity check" in caplog.text

    caplog.clear()
    with (
        patch(
            "homeassistant.components.recorder.util.last_run_was_recently_clean",
            side_effect=sqlite3.DatabaseError,
        ),
        pytest.raises(sqlite3.DatabaseError),
    ):
        util.run_checks_on_open_db("fake_db_path", cursor)

    caplog.clear()
    with (
        patch(
            "homeassistant.components.recorder.util.last_run_was_recently_clean",
            side_effect=sqlite3.DatabaseError,
        ),
        pytest.raises(sqlite3.DatabaseError),
    ):
        util.run_checks_on_open_db("fake_db_path", cursor)

    cursor.execute("DROP TABLE events;")

    caplog.clear()
    with pytest.raises(sqlite3.DatabaseError):
        util.run_checks_on_open_db("fake_db_path", cursor)

    caplog.clear()
    with pytest.raises(sqlite3.DatabaseError):
        util.run_checks_on_open_db("fake_db_path", cursor)


async def test_end_incomplete_runs(
    hass: HomeAssistant, setup_recorder: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure we can end incomplete runs."""
    with session_scope(hass=hass) as session:
        run_info = run_information_with_session(session)
        assert isinstance(run_info, RecorderRuns)
        assert run_info.closed_incorrect is False

        now = dt_util.utcnow()
        end_incomplete_runs(session, now)
        run_info = run_information_with_session(session)
        assert run_info.closed_incorrect is True
        assert process_timestamp(run_info.end) == now
        session.flush()

        later = dt_util.utcnow()
        end_incomplete_runs(session, later)
        run_info = run_information_with_session(session)
        assert process_timestamp(run_info.end) == now

    assert "Ended unfinished session" in caplog.text


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_periodic_db_cleanups(
    hass: HomeAssistant, setup_recorder: None, recorder_db_url: str
) -> None:
    """Test periodic db cleanups.

    This test is specific for SQLite.
    """
    with patch.object(util.get_instance(hass).engine, "connect") as connect_mock:
        util.periodic_db_cleanups(util.get_instance(hass))

    text_obj = connect_mock.return_value.__enter__.return_value.execute.mock_calls[0][
        1
    ][0]
    assert isinstance(text_obj, TextClause)
    assert str(text_obj) == "PRAGMA wal_checkpoint(TRUNCATE);"


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
@pytest.mark.parametrize("persistent_database", [True])
async def test_write_lock_db(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
) -> None:
    """Test database write lock.

    This is only supported for SQLite.

    Use file DB, in memory DB cannot do write locks.
    """

    config = {recorder.CONF_DB_URL: recorder_db_url + "?timeout=0.1"}
    instance = await async_setup_recorder_instance(hass, config)
    await hass.async_block_till_done()

    def _drop_table():
        with instance.engine.connect() as connection:
            connection.execute(text("DROP TABLE events;"))

    instance.recorder_and_worker_thread_ids.add(threading.get_ident())
    with util.write_lock_db_sqlite(instance), pytest.raises(OperationalError):
        # Database should be locked now, try writing SQL command
        # This needs to be called in another thread since
        # the lock method is BEGIN IMMEDIATE and since we have
        # a connection per thread with sqlite now, we cannot do it
        # in the same thread as the one holding the lock since it
        # would be allowed to proceed as the goal is to prevent
        # all the other threads from accessing the database
        await instance.async_add_executor_job(_drop_table)


def test_is_second_sunday() -> None:
    """Test we can find the second sunday of the month."""
    assert is_second_sunday(datetime(2022, 1, 9, 0, 0, 0, tzinfo=dt_util.UTC)) is True
    assert is_second_sunday(datetime(2022, 2, 13, 0, 0, 0, tzinfo=dt_util.UTC)) is True
    assert is_second_sunday(datetime(2022, 3, 13, 0, 0, 0, tzinfo=dt_util.UTC)) is True
    assert is_second_sunday(datetime(2022, 4, 10, 0, 0, 0, tzinfo=dt_util.UTC)) is True
    assert is_second_sunday(datetime(2022, 5, 8, 0, 0, 0, tzinfo=dt_util.UTC)) is True

    assert is_second_sunday(datetime(2022, 1, 10, 0, 0, 0, tzinfo=dt_util.UTC)) is False


def test_build_mysqldb_conv() -> None:
    """Test building the MySQLdb connect conv param."""
    mock_converters = Mock(conversions={"original": "preserved"})
    mock_constants = Mock(FIELD_TYPE=Mock(DATETIME="DATETIME"))
    with patch.dict(
        "sys.modules",
        **{"MySQLdb.constants": mock_constants, "MySQLdb.converters": mock_converters},
    ):
        conv = util.build_mysqldb_conv()

    assert conv["original"] == "preserved"
    assert conv["DATETIME"]("INVALID") is None
    assert conv["DATETIME"]("2022-05-13T22:33:12.741") == datetime(
        2022, 5, 13, 22, 33, 12, 741000, tzinfo=None
    )


@patch("homeassistant.components.recorder.util.QUERY_RETRY_WAIT", 0)
async def test_execute_stmt_lambda_element(
    hass: HomeAssistant,
    setup_recorder: None,
) -> None:
    """Test executing with execute_stmt_lambda_element."""
    instance = recorder.get_instance(hass)
    hass.states.async_set("sensor.on", "on")
    new_state = hass.states.get("sensor.on")
    await async_wait_recording_done(hass)
    now = dt_util.utcnow()
    tomorrow = now + timedelta(days=1)
    one_week_from_now = now + timedelta(days=7)
    all_calls = 0

    class MockExecutor:
        def __init__(self, stmt) -> None:
            assert isinstance(stmt, StatementLambdaElement)

        def all(self):
            nonlocal all_calls
            all_calls += 1
            if all_calls == 2:
                return ["mock_row"]
            raise SQLAlchemyError

    with session_scope(hass=hass) as session:
        # No time window, we always get a list
        metadata_id = instance.states_meta_manager.get("sensor.on", session, True)
        start_time_ts = dt_util.utcnow().timestamp()
        stmt = lambda_stmt(
            lambda: _get_single_entity_start_time_stmt(
                start_time_ts, metadata_id, False, False, False
            )
        )
        rows = util.execute_stmt_lambda_element(session, stmt)
        assert isinstance(rows, list)
        assert rows[0].state == new_state.state
        assert rows[0].metadata_id == metadata_id

        # Time window >= 2 days, we get a ChunkedIteratorResult
        rows = util.execute_stmt_lambda_element(session, stmt, now, one_week_from_now)
        assert isinstance(rows, ChunkedIteratorResult)
        row = next(rows)
        assert row.state == new_state.state
        assert row.metadata_id == metadata_id

        # Time window >= 2 days, we should not get a ChunkedIteratorResult
        # because orm_rows=False
        rows = util.execute_stmt_lambda_element(
            session, stmt, now, one_week_from_now, orm_rows=False
        )
        assert not isinstance(rows, ChunkedIteratorResult)
        row = next(rows)
        assert row.state == new_state.state
        assert row.metadata_id == metadata_id

        # Time window < 2 days, we get a list
        rows = util.execute_stmt_lambda_element(session, stmt, now, tomorrow)
        assert isinstance(rows, list)
        assert rows[0].state == new_state.state
        assert rows[0].metadata_id == metadata_id

        with patch.object(session, "execute", MockExecutor):
            rows = util.execute_stmt_lambda_element(session, stmt, now, tomorrow)
            assert rows == ["mock_row"]


@pytest.mark.freeze_time(datetime(2022, 10, 21, 7, 25, tzinfo=UTC))
async def test_resolve_period(hass: HomeAssistant) -> None:
    """Test statistic_during_period."""

    now = dt_util.utcnow()

    start_t, end_t = resolve_period({"calendar": {"period": "hour"}})
    assert start_t.isoformat() == "2022-10-21T07:00:00+00:00"
    assert end_t.isoformat() == "2022-10-21T08:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "hour"}})
    assert start_t.isoformat() == "2022-10-21T07:00:00+00:00"
    assert end_t.isoformat() == "2022-10-21T08:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "hour", "offset": -1}})
    assert start_t.isoformat() == "2022-10-21T06:00:00+00:00"
    assert end_t.isoformat() == "2022-10-21T07:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "day"}})
    assert start_t.isoformat() == "2022-10-21T07:00:00+00:00"
    assert end_t.isoformat() == "2022-10-22T07:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "day", "offset": -1}})
    assert start_t.isoformat() == "2022-10-20T07:00:00+00:00"
    assert end_t.isoformat() == "2022-10-21T07:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "week"}})
    assert start_t.isoformat() == "2022-10-17T07:00:00+00:00"
    assert end_t.isoformat() == "2022-10-24T07:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "week", "offset": -1}})
    assert start_t.isoformat() == "2022-10-10T07:00:00+00:00"
    assert end_t.isoformat() == "2022-10-17T07:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "month"}})
    assert start_t.isoformat() == "2022-10-01T07:00:00+00:00"
    assert end_t.isoformat() == "2022-11-01T07:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "month", "offset": -1}})
    assert start_t.isoformat() == "2022-09-01T07:00:00+00:00"
    assert end_t.isoformat() == "2022-10-01T07:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "year"}})
    assert start_t.isoformat() == "2022-01-01T08:00:00+00:00"
    assert end_t.isoformat() == "2023-01-01T08:00:00+00:00"

    start_t, end_t = resolve_period({"calendar": {"period": "year", "offset": -1}})
    assert start_t.isoformat() == "2021-01-01T08:00:00+00:00"
    assert end_t.isoformat() == "2022-01-01T08:00:00+00:00"

    # Fixed period
    assert resolve_period({}) == (None, None)

    assert resolve_period({"fixed_period": {"end_time": now}}) == (None, now)

    assert resolve_period({"fixed_period": {"start_time": now}}) == (now, None)

    assert resolve_period({"fixed_period": {"end_time": now, "start_time": now}}) == (
        now,
        now,
    )

    # Rolling window
    assert resolve_period(
        {"rolling_window": {"duration": timedelta(hours=1, minutes=25)}}
    ) == (now - timedelta(hours=1, minutes=25), now)

    assert resolve_period(
        {
            "rolling_window": {
                "duration": timedelta(hours=1),
                "offset": timedelta(minutes=-25),
            }
        }
    ) == (now - timedelta(hours=1, minutes=25), now - timedelta(minutes=25))


NonRetryable = OperationalError(None, None, BaseException())
Retryable = OperationalError(None, None, BaseException(RETRYABLE_MYSQL_ERRORS[0], ""))


@pytest.mark.parametrize(
    ("side_effect", "dialect", "expected_result", "num_calls"),
    [
        (None, SupportedDialect.MYSQL, does_not_raise(), 1),
        (ValueError, SupportedDialect.MYSQL, pytest.raises(ValueError), 1),
        (NonRetryable, SupportedDialect.MYSQL, pytest.raises(OperationalError), 1),
        (Retryable, SupportedDialect.MYSQL, pytest.raises(OperationalError), 5),
        (NonRetryable, SupportedDialect.SQLITE, pytest.raises(OperationalError), 1),
        (Retryable, SupportedDialect.SQLITE, pytest.raises(OperationalError), 1),
    ],
)
def test_database_job_retry_wrapper(
    side_effect: Any,
    dialect: str,
    expected_result: AbstractContextManager,
    num_calls: int,
) -> None:
    """Test database_job_retry_wrapper."""

    instance = Mock()
    instance.db_retry_wait = 0
    instance.engine.dialect.name = dialect
    mock_job = Mock(side_effect=side_effect)

    @database_job_retry_wrapper(description="test")
    def job(instance, *args, **kwargs) -> None:
        mock_job()

    with expected_result:
        job(instance)

    assert len(mock_job.mock_calls) == num_calls


@pytest.mark.parametrize(
    ("side_effect", "dialect", "retval", "expected_result"),
    [
        (None, SupportedDialect.MYSQL, False, does_not_raise()),
        (None, SupportedDialect.MYSQL, True, does_not_raise()),
        (ValueError, SupportedDialect.MYSQL, False, pytest.raises(ValueError)),
        (NonRetryable, SupportedDialect.MYSQL, True, does_not_raise()),
        (Retryable, SupportedDialect.MYSQL, False, does_not_raise()),
        (NonRetryable, SupportedDialect.SQLITE, True, does_not_raise()),
        (Retryable, SupportedDialect.SQLITE, True, does_not_raise()),
    ],
)
def test_retryable_database_job(
    side_effect: Any,
    retval: bool,
    expected_result: AbstractContextManager,
    dialect: str,
) -> None:
    """Test retryable_database_job."""

    instance = Mock()
    instance.db_retry_wait = 0
    instance.engine.dialect.name = dialect
    mock_job = Mock(side_effect=side_effect)

    @retryable_database_job(description="test")
    def job(instance, *args, **kwargs) -> bool:
        mock_job()
        return retval

    with expected_result:
        assert job(instance) == retval

    assert len(mock_job.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "dialect", "retval", "expected_result"),
    [
        (None, SupportedDialect.MYSQL, False, does_not_raise()),
        (None, SupportedDialect.MYSQL, True, does_not_raise()),
        (ValueError, SupportedDialect.MYSQL, False, pytest.raises(ValueError)),
        (NonRetryable, SupportedDialect.MYSQL, True, does_not_raise()),
        (Retryable, SupportedDialect.MYSQL, False, does_not_raise()),
        (NonRetryable, SupportedDialect.SQLITE, True, does_not_raise()),
        (Retryable, SupportedDialect.SQLITE, True, does_not_raise()),
    ],
)
def test_retryable_database_job_method(
    side_effect: Any,
    retval: bool,
    expected_result: AbstractContextManager,
    dialect: str,
) -> None:
    """Test retryable_database_job_method."""

    instance = Mock()
    instance.db_retry_wait = 0
    instance.engine.dialect.name = dialect
    mock_job = Mock(side_effect=side_effect)

    class Test:
        @retryable_database_job_method(description="test")
        def job(self, instance, *args, **kwargs) -> bool:
            mock_job()
            return retval

    test = Test()
    with expected_result:
        assert test.job(instance) == retval

    assert len(mock_job.mock_calls) == 1
