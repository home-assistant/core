"""Test util methods."""
from datetime import datetime, timedelta
import os
import sqlite3
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.engine.result import ChunkedIteratorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.lambdas import StatementLambdaElement

from homeassistant.components import recorder
from homeassistant.components.recorder import history, util
from homeassistant.components.recorder.const import SQLITE_URL_PREFIX
from homeassistant.components.recorder.db_schema import RecorderRuns
from homeassistant.components.recorder.models import UnsupportedDialect
from homeassistant.components.recorder.util import (
    end_incomplete_runs,
    is_second_sunday,
    session_scope,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import corrupt_db_file, run_information_with_session

from tests.common import SetupRecorderInstanceT, async_test_home_assistant
from tests.components.recorder.common import wait_recording_done


def test_session_scope_not_setup(hass_recorder):
    """Try to create a session scope when not setup."""
    hass = hass_recorder()
    with patch.object(
        util.get_instance(hass), "get_session", return_value=None
    ), pytest.raises(RuntimeError):
        with util.session_scope(hass=hass):
            pass


def test_recorder_bad_commit(hass_recorder):
    """Bad _commit should retry 3 times."""
    hass = hass_recorder()

    def work(session):
        """Bad work."""
        session.execute(text("select * from notthere"))

    with patch(
        "homeassistant.components.recorder.core.time.sleep"
    ) as e_mock, util.session_scope(hass=hass) as session:
        res = util.commit(session, work)
    assert res is False
    assert e_mock.call_count == 3


def test_recorder_bad_execute(hass_recorder):
    """Bad execute, retry 3 times."""
    from sqlalchemy.exc import SQLAlchemyError

    hass_recorder()

    def to_native(validate_entity_id=True):
        """Raise exception."""
        raise SQLAlchemyError()

    mck1 = MagicMock()
    mck1.to_native = to_native

    with pytest.raises(SQLAlchemyError), patch(
        "homeassistant.components.recorder.core.time.sleep"
    ) as e_mock:
        util.execute((mck1,), to_native=True)

    assert e_mock.call_count == 2


def test_validate_or_move_away_sqlite_database(hass, tmpdir, caplog):
    """Ensure a malformed sqlite database is moved away."""

    test_dir = tmpdir.mkdir("test_validate_or_move_away_sqlite_database")
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


async def test_last_run_was_recently_clean(
    loop, async_setup_recorder_instance: SetupRecorderInstanceT, tmp_path
):
    """Test we can check if the last recorder run was recently clean."""
    config = {
        recorder.CONF_DB_URL: "sqlite:///" + str(tmp_path / "pytest.db"),
        recorder.CONF_COMMIT_INTERVAL: 1,
    }
    hass = await async_test_home_assistant(None)

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

    with patch(
        "homeassistant.components.recorder.util.last_run_was_recently_clean",
        wraps=_last_run_was_recently_clean,
    ) as last_run_was_recently_clean_mock:
        hass = await async_test_home_assistant(None)
        await async_setup_recorder_instance(hass, config)
        last_run_was_recently_clean_mock.assert_called_once()
        assert return_values[-1] is True

    # Restart HA with a long downtime, last_run_was_recently_clean should return False
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await hass.async_stop()

    thirty_min_future_time = dt_util.utcnow() + timedelta(minutes=30)

    with patch(
        "homeassistant.components.recorder.util.last_run_was_recently_clean",
        wraps=_last_run_was_recently_clean,
    ) as last_run_was_recently_clean_mock, patch(
        "homeassistant.components.recorder.core.dt_util.utcnow",
        return_value=thirty_min_future_time,
    ):
        hass = await async_test_home_assistant(None)
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
def test_setup_connection_for_dialect_mysql(mysql_version):
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

    assert len(execute_args) == 2
    assert execute_args[0] == "SET session wait_timeout=28800"
    assert execute_args[1] == "SELECT VERSION()"


@pytest.mark.parametrize(
    "sqlite_version",
    ["3.31.0"],
)
def test_setup_connection_for_dialect_sqlite(sqlite_version):
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

    util.setup_connection_for_dialect(instance_mock, "sqlite", dbapi_connection, True)

    assert len(execute_args) == 5
    assert execute_args[0] == "PRAGMA journal_mode=WAL"
    assert execute_args[1] == "SELECT sqlite_version()"
    assert execute_args[2] == "PRAGMA cache_size = -16384"
    assert execute_args[3] == "PRAGMA synchronous=NORMAL"
    assert execute_args[4] == "PRAGMA foreign_keys=ON"

    execute_args = []
    util.setup_connection_for_dialect(instance_mock, "sqlite", dbapi_connection, False)

    assert len(execute_args) == 3
    assert execute_args[0] == "PRAGMA cache_size = -16384"
    assert execute_args[1] == "PRAGMA synchronous=NORMAL"
    assert execute_args[2] == "PRAGMA foreign_keys=ON"


@pytest.mark.parametrize(
    "sqlite_version",
    ["3.31.0"],
)
def test_setup_connection_for_dialect_sqlite_zero_commit_interval(
    sqlite_version,
):
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

    util.setup_connection_for_dialect(instance_mock, "sqlite", dbapi_connection, True)

    assert len(execute_args) == 5
    assert execute_args[0] == "PRAGMA journal_mode=WAL"
    assert execute_args[1] == "SELECT sqlite_version()"
    assert execute_args[2] == "PRAGMA cache_size = -16384"
    assert execute_args[3] == "PRAGMA synchronous=FULL"
    assert execute_args[4] == "PRAGMA foreign_keys=ON"

    execute_args = []
    util.setup_connection_for_dialect(instance_mock, "sqlite", dbapi_connection, False)

    assert len(execute_args) == 3
    assert execute_args[0] == "PRAGMA cache_size = -16384"
    assert execute_args[1] == "PRAGMA synchronous=FULL"
    assert execute_args[2] == "PRAGMA foreign_keys=ON"


@pytest.mark.parametrize(
    "mysql_version,message",
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
def test_fail_outdated_mysql(caplog, mysql_version, message):
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
def test_supported_mysql(caplog, mysql_version):
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
    "pgsql_version,message",
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
def test_fail_outdated_pgsql(caplog, pgsql_version, message):
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
def test_supported_pgsql(caplog, pgsql_version):
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

    util.setup_connection_for_dialect(
        instance_mock, "postgresql", dbapi_connection, True
    )

    assert "minimum supported version" not in caplog.text


@pytest.mark.parametrize(
    "sqlite_version,message",
    [
        (
            "3.30.0",
            "Version 3.30.0 of SQLite is not supported; minimum supported version is 3.31.0.",
        ),
        (
            "2.0.0",
            "Version 2.0.0 of SQLite is not supported; minimum supported version is 3.31.0.",
        ),
        (
            "dogs",
            "Version dogs of SQLite is not supported; minimum supported version is 3.31.0.",
        ),
    ],
)
def test_fail_outdated_sqlite(caplog, sqlite_version, message):
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
def test_supported_sqlite(caplog, sqlite_version):
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

    util.setup_connection_for_dialect(instance_mock, "sqlite", dbapi_connection, True)

    assert "minimum supported version" not in caplog.text


@pytest.mark.parametrize(
    "dialect,message",
    [
        ("mssql", "Database mssql is not supported"),
        ("oracle", "Database oracle is not supported"),
        ("some_db", "Database some_db is not supported"),
    ],
)
def test_warn_unsupported_dialect(caplog, dialect, message):
    """Test setting up the connection for an outdated sqlite version."""
    instance_mock = MagicMock()
    dbapi_connection = MagicMock()

    with pytest.raises(UnsupportedDialect):
        util.setup_connection_for_dialect(
            instance_mock, dialect, dbapi_connection, True
        )

    assert message in caplog.text


def test_basic_sanity_check(hass_recorder):
    """Test the basic sanity checks with a missing table."""
    hass = hass_recorder()

    cursor = util.get_instance(hass).engine.raw_connection().cursor()

    assert util.basic_sanity_check(cursor) is True

    cursor.execute("DROP TABLE states;")

    with pytest.raises(sqlite3.DatabaseError):
        util.basic_sanity_check(cursor)


def test_combined_checks(hass_recorder, caplog):
    """Run Checks on the open database."""
    hass = hass_recorder()
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
    with patch(
        "homeassistant.components.recorder.util.last_run_was_recently_clean",
        side_effect=sqlite3.DatabaseError,
    ), pytest.raises(sqlite3.DatabaseError):
        util.run_checks_on_open_db("fake_db_path", cursor)

    caplog.clear()
    with patch(
        "homeassistant.components.recorder.util.last_run_was_recently_clean",
        side_effect=sqlite3.DatabaseError,
    ), pytest.raises(sqlite3.DatabaseError):
        util.run_checks_on_open_db("fake_db_path", cursor)

    cursor.execute("DROP TABLE events;")

    caplog.clear()
    with pytest.raises(sqlite3.DatabaseError):
        util.run_checks_on_open_db("fake_db_path", cursor)

    caplog.clear()
    with pytest.raises(sqlite3.DatabaseError):
        util.run_checks_on_open_db("fake_db_path", cursor)


def test_end_incomplete_runs(hass_recorder, caplog):
    """Ensure we can end incomplete runs."""
    hass = hass_recorder()

    with session_scope(hass=hass) as session:
        run_info = run_information_with_session(session)
        assert isinstance(run_info, RecorderRuns)
        assert run_info.closed_incorrect is False

        now = dt_util.utcnow()
        now_without_tz = now.replace(tzinfo=None)
        end_incomplete_runs(session, now)
        run_info = run_information_with_session(session)
        assert run_info.closed_incorrect is True
        assert run_info.end == now_without_tz
        session.flush()

        later = dt_util.utcnow()
        end_incomplete_runs(session, later)
        run_info = run_information_with_session(session)
        assert run_info.end == now_without_tz

    assert "Ended unfinished session" in caplog.text


def test_periodic_db_cleanups(hass_recorder):
    """Test periodic db cleanups."""
    hass = hass_recorder()
    with patch.object(util.get_instance(hass).engine, "connect") as connect_mock:
        util.periodic_db_cleanups(util.get_instance(hass))

    text_obj = connect_mock.return_value.__enter__.return_value.execute.mock_calls[0][
        1
    ][0]
    assert isinstance(text_obj, TextClause)
    assert str(text_obj) == "PRAGMA wal_checkpoint(TRUNCATE);"


@patch("homeassistant.components.recorder.pool.check_loop")
async def test_write_lock_db(
    skip_check_loop,
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    tmp_path,
):
    """Test database write lock."""
    from sqlalchemy.exc import OperationalError

    # Use file DB, in memory DB cannot do write locks.
    config = {
        recorder.CONF_DB_URL: "sqlite:///" + str(tmp_path / "pytest.db?timeout=0.1")
    }
    instance = await async_setup_recorder_instance(hass, config)
    await hass.async_block_till_done()

    def _drop_table():
        with instance.engine.connect() as connection:
            connection.execute(text("DROP TABLE events;"))

    with util.write_lock_db_sqlite(instance):
        # Database should be locked now, try writing SQL command
        with pytest.raises(OperationalError):
            # This needs to be called in another thread since
            # the lock method is BEGIN IMMEDIATE and since we have
            # a connection per thread with sqlite now, we cannot do it
            # in the same thread as the one holding the lock since it
            # would be allowed to proceed as the goal is to prevent
            # all the other threads from accessing the database
            await hass.async_add_executor_job(_drop_table)


def test_is_second_sunday():
    """Test we can find the second sunday of the month."""
    assert is_second_sunday(datetime(2022, 1, 9, 0, 0, 0, tzinfo=dt_util.UTC)) is True
    assert is_second_sunday(datetime(2022, 2, 13, 0, 0, 0, tzinfo=dt_util.UTC)) is True
    assert is_second_sunday(datetime(2022, 3, 13, 0, 0, 0, tzinfo=dt_util.UTC)) is True
    assert is_second_sunday(datetime(2022, 4, 10, 0, 0, 0, tzinfo=dt_util.UTC)) is True
    assert is_second_sunday(datetime(2022, 5, 8, 0, 0, 0, tzinfo=dt_util.UTC)) is True

    assert is_second_sunday(datetime(2022, 1, 10, 0, 0, 0, tzinfo=dt_util.UTC)) is False


def test_build_mysqldb_conv():
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
def test_execute_stmt_lambda_element(hass_recorder):
    """Test executing with execute_stmt_lambda_element."""
    hass = hass_recorder()
    instance = recorder.get_instance(hass)
    hass.states.set("sensor.on", "on")
    new_state = hass.states.get("sensor.on")
    wait_recording_done(hass)
    now = dt_util.utcnow()
    tomorrow = now + timedelta(days=1)
    one_week_from_now = now + timedelta(days=7)

    class MockExecutor:
        def __init__(self, stmt):
            assert isinstance(stmt, StatementLambdaElement)
            self.calls = 0

        def all(self):
            self.calls += 1
            if self.calls == 2:
                return ["mock_row"]
            raise SQLAlchemyError

    with session_scope(hass=hass) as session:
        # No time window, we always get a list
        stmt = history._get_single_entity_states_stmt(
            instance.schema_version, dt_util.utcnow(), "sensor.on", False
        )
        rows = util.execute_stmt_lambda_element(session, stmt)
        assert isinstance(rows, list)
        assert rows[0].state == new_state.state
        assert rows[0].entity_id == new_state.entity_id

        # Time window >= 2 days, we get a ChunkedIteratorResult
        rows = util.execute_stmt_lambda_element(session, stmt, now, one_week_from_now)
        assert isinstance(rows, ChunkedIteratorResult)
        row = next(rows)
        assert row.state == new_state.state
        assert row.entity_id == new_state.entity_id

        # Time window < 2 days, we get a list
        rows = util.execute_stmt_lambda_element(session, stmt, now, tomorrow)
        assert isinstance(rows, list)
        assert rows[0].state == new_state.state
        assert rows[0].entity_id == new_state.entity_id

        with patch.object(session, "execute", MockExecutor):
            rows = util.execute_stmt_lambda_element(session, stmt, now, tomorrow)
            assert rows == ["mock_row"]
