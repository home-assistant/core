"""The tests for the Recorder component."""

import datetime
import importlib
import sqlite3
import sys
import threading
from unittest.mock import Mock, PropertyMock, call, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import (
    DatabaseError,
    InternalError,
    OperationalError,
    ProgrammingError,
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import persistent_notification as pn, recorder
from homeassistant.components.recorder import db_schema, migration
from homeassistant.components.recorder.db_schema import (
    SCHEMA_VERSION,
    RecorderRuns,
    States,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
import homeassistant.util.dt as dt_util

from .common import async_wait_recording_done, create_engine_test

from tests.common import async_fire_time_changed

ORIG_TZ = dt_util.DEFAULT_TIME_ZONE


def _get_native_states(hass, entity_id):
    with session_scope(hass=hass) as session:
        return [
            state.to_native()
            for state in session.query(States).filter(States.entity_id == entity_id)
        ]


async def test_schema_update_calls(recorder_db_url: str, hass: HomeAssistant) -> None:
    """Test that schema migrations occur in correct order."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.core.create_engine",
        new=create_engine_test,
    ), patch(
        "homeassistant.components.recorder.migration._apply_update",
        wraps=migration._apply_update,
    ) as update:
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": recorder_db_url}}
        )
        await async_wait_recording_done(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    instance = recorder.get_instance(hass)
    engine = instance.engine
    session_maker = instance.get_session
    update.assert_has_calls(
        [
            call(instance, hass, engine, session_maker, version + 1, 0)
            for version in range(0, db_schema.SCHEMA_VERSION)
        ]
    )


async def test_migration_in_progress(recorder_db_url: str, hass: HomeAssistant) -> None:
    """Test that we can check for migration in progress."""
    if recorder_db_url.startswith("mysql://"):
        # The database drop at the end of this test currently hangs on MySQL
        # because the post migration is still in progress in the background
        # which results in a deadlock in InnoDB. This behavior is not likely
        # to happen in real life because the database does not get dropped
        # in normal operation.
        return

    assert recorder.util.async_migration_in_progress(hass) is False

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.core.create_engine",
        new=create_engine_test,
    ):
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": recorder_db_url}}
        )
        await recorder.get_instance(hass).async_migration_event.wait()
        assert recorder.util.async_migration_in_progress(hass) is True
        await async_wait_recording_done(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    assert recorder.get_instance(hass).schema_version == SCHEMA_VERSION


async def test_database_migration_failed(
    recorder_db_url: str, hass: HomeAssistant
) -> None:
    """Test we notify if the migration fails."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.core.create_engine",
        new=create_engine_test,
    ), patch(
        "homeassistant.components.recorder.migration._apply_update",
        side_effect=ValueError,
    ), patch(
        "homeassistant.components.persistent_notification.create", side_effect=pn.create
    ) as mock_create, patch(
        "homeassistant.components.persistent_notification.dismiss",
        side_effect=pn.dismiss,
    ) as mock_dismiss:
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": recorder_db_url}}
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        await hass.async_add_executor_job(recorder.get_instance(hass).join)
        await hass.async_block_till_done()

    assert recorder.util.async_migration_in_progress(hass) is False
    assert len(mock_create.mock_calls) == 2
    assert len(mock_dismiss.mock_calls) == 1


async def test_database_migration_encounters_corruption(
    recorder_db_url: str, hass: HomeAssistant
) -> None:
    """Test we move away the database if its corrupt."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        # This test is specific for SQLite, wiping the database on error only happens
        # with SQLite.
        return

    assert recorder.util.async_migration_in_progress(hass) is False

    sqlite3_exception = DatabaseError("statement", {}, [])
    sqlite3_exception.__cause__ = sqlite3.DatabaseError()

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.migration._schema_is_current",
        side_effect=[False],
    ), patch(
        "homeassistant.components.recorder.migration.migrate_schema",
        side_effect=sqlite3_exception,
    ), patch(
        "homeassistant.components.recorder.core.move_away_broken_database"
    ) as move_away, patch(
        "homeassistant.components.recorder.Recorder._schedule_compile_missing_statistics",
    ):
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": recorder_db_url}}
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await async_wait_recording_done(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    assert move_away.called


async def test_database_migration_encounters_corruption_not_sqlite(
    recorder_db_url: str, hass: HomeAssistant
) -> None:
    """Test we fail on database error when we cannot recover."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.migration._schema_is_current",
        side_effect=[False],
    ), patch(
        "homeassistant.components.recorder.migration.migrate_schema",
        side_effect=DatabaseError("statement", {}, []),
    ), patch(
        "homeassistant.components.recorder.core.move_away_broken_database"
    ) as move_away, patch(
        "homeassistant.components.persistent_notification.create", side_effect=pn.create
    ) as mock_create, patch(
        "homeassistant.components.persistent_notification.dismiss",
        side_effect=pn.dismiss,
    ) as mock_dismiss:
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": recorder_db_url}}
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        await hass.async_add_executor_job(recorder.get_instance(hass).join)
        await hass.async_block_till_done()

    assert recorder.util.async_migration_in_progress(hass) is False
    assert not move_away.called
    assert len(mock_create.mock_calls) == 2
    assert len(mock_dismiss.mock_calls) == 1


async def test_events_during_migration_are_queued(
    recorder_db_url: str, hass: HomeAssistant
) -> None:
    """Test that events during migration are queued."""

    assert recorder.util.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.ALLOW_IN_MEMORY_DB",
        True,
    ), patch(
        "homeassistant.components.recorder.core.create_engine",
        new=create_engine_test,
    ):
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(
            hass,
            "recorder",
            {"recorder": {"db_url": recorder_db_url, "commit_interval": 0}},
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=2))
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=4))
        await recorder.get_instance(hass).async_recorder_ready.wait()
        await async_wait_recording_done(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    db_states = await recorder.get_instance(hass).async_add_executor_job(
        _get_native_states, hass, "my.entity"
    )
    assert len(db_states) == 2


async def test_events_during_migration_queue_exhausted(
    recorder_db_url: str, hass: HomeAssistant
) -> None:
    """Test that events during migration takes so long the queue is exhausted."""

    assert recorder.util.async_migration_in_progress(hass) is False

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.core.create_engine",
        new=create_engine_test,
    ), patch.object(recorder.core, "MAX_QUEUE_BACKLOG", 1):
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(
            hass,
            "recorder",
            {"recorder": {"db_url": recorder_db_url, "commit_interval": 0}},
        )
        hass.states.async_set("my.entity", "on", {})
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=2))
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=4))
        await hass.async_block_till_done()
        hass.states.async_set("my.entity", "off", {})
        await recorder.get_instance(hass).async_recorder_ready.wait()
        await async_wait_recording_done(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    db_states = await recorder.get_instance(hass).async_add_executor_job(
        _get_native_states, hass, "my.entity"
    )
    assert len(db_states) == 1
    hass.states.async_set("my.entity", "on", {})
    await async_wait_recording_done(hass)
    db_states = await recorder.get_instance(hass).async_add_executor_job(
        _get_native_states, hass, "my.entity"
    )
    assert len(db_states) == 2


@pytest.mark.parametrize(
    ("start_version", "live"),
    [(0, True), (16, True), (18, True), (22, True), (25, True)],
)
async def test_schema_migrate(
    recorder_db_url: str, hass: HomeAssistant, start_version, live
) -> None:
    """Test the full schema migration logic.

    We're just testing that the logic can execute successfully here without
    throwing exceptions. Maintaining a set of assertions based on schema
    inspection could quickly become quite cumbersome.
    """

    migration_done = threading.Event()
    migration_stall = threading.Event()
    migration_version = None
    real_migrate_schema = recorder.migration.migrate_schema
    real_apply_update = recorder.migration._apply_update
    real_create_index = recorder.migration._create_index
    create_calls = 0

    def _create_engine_test(*args, **kwargs):
        """Test version of create_engine that initializes with old schema.

        This simulates an existing db with the old schema.
        """
        module = f"tests.components.recorder.db_schema_{str(start_version)}"
        importlib.import_module(module)
        old_models = sys.modules[module]
        engine = create_engine(*args, **kwargs)
        old_models.Base.metadata.create_all(engine)
        if start_version > 0:
            with Session(engine) as session:
                session.add(
                    recorder.db_schema.SchemaChanges(schema_version=start_version)
                )
                session.commit()
        return engine

    def _mock_setup_run(self):
        self.run_info = RecorderRuns(
            start=self.run_history.recording_start, created=dt_util.utcnow()
        )

    def _instrument_migrate_schema(*args):
        """Control migration progress and check results."""
        nonlocal migration_done
        nonlocal migration_version
        try:
            real_migrate_schema(*args)
        except Exception:
            migration_done.set()
            raise

        # Check and report the outcome of the migration; if migration fails
        # the recorder will silently create a new database.
        with session_scope(hass=hass) as session:
            res = (
                session.query(db_schema.SchemaChanges)
                .order_by(db_schema.SchemaChanges.change_id.desc())
                .first()
            )
            migration_version = res.schema_version
        migration_done.set()

    def _instrument_apply_update(*args):
        """Control migration progress."""
        nonlocal migration_stall
        migration_stall.wait()
        real_apply_update(*args)

    def _sometimes_failing_create_index(*args):
        """Make the first index create raise a retryable error to ensure we retry."""
        if recorder_db_url.startswith("mysql://"):
            nonlocal create_calls
            if create_calls < 1:
                create_calls += 1
                mysql_exception = OperationalError("statement", {}, [])
                mysql_exception.orig = Exception(1205, "retryable")
                raise mysql_exception
        real_create_index(*args)

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.core.create_engine",
        new=_create_engine_test,
    ), patch(
        "homeassistant.components.recorder.Recorder._setup_run",
        side_effect=_mock_setup_run,
        autospec=True,
    ) as setup_run, patch(
        "homeassistant.components.recorder.migration.migrate_schema",
        wraps=_instrument_migrate_schema,
    ), patch(
        "homeassistant.components.recorder.migration._apply_update",
        wraps=_instrument_apply_update,
    ) as apply_update_mock, patch(
        "homeassistant.components.recorder.util.time.sleep"
    ), patch(
        "homeassistant.components.recorder.migration._create_index",
        wraps=_sometimes_failing_create_index,
    ), patch(
        "homeassistant.components.recorder.Recorder._schedule_compile_missing_statistics",
    ), patch(
        "homeassistant.components.recorder.Recorder._process_state_changed_event_into_session",
    ), patch(
        "homeassistant.components.recorder.Recorder._process_non_state_changed_event_into_session",
    ), patch(
        "homeassistant.components.recorder.Recorder._pre_process_startup_tasks",
    ):
        recorder_helper.async_initialize_recorder(hass)
        hass.async_create_task(
            async_setup_component(
                hass, "recorder", {"recorder": {"db_url": recorder_db_url}}
            )
        )
        await recorder_helper.async_wait_recorder(hass)

        assert recorder.util.async_migration_in_progress(hass) is True
        assert recorder.util.async_migration_is_live(hass) == live
        migration_stall.set()
        await hass.async_block_till_done()
        await hass.async_add_executor_job(migration_done.wait)
        await async_wait_recording_done(hass)
        assert migration_version == db_schema.SCHEMA_VERSION
        assert setup_run.called
        assert recorder.util.async_migration_in_progress(hass) is not True
        assert apply_update_mock.called


def test_invalid_update(hass: HomeAssistant) -> None:
    """Test that an invalid new version raises an exception."""
    with pytest.raises(ValueError):
        migration._apply_update(Mock(), hass, Mock(), Mock(), -1, 0)


@pytest.mark.parametrize(
    ("engine_type", "substr"),
    [
        ("postgresql", "ALTER event_type TYPE VARCHAR(64)"),
        ("mssql", "ALTER COLUMN event_type VARCHAR(64)"),
        ("mysql", "MODIFY event_type VARCHAR(64)"),
        ("sqlite", None),
    ],
)
def test_modify_column(engine_type, substr) -> None:
    """Test that modify column generates the expected query."""
    connection = Mock()
    session = Mock()
    session.connection = Mock(return_value=connection)
    instance = Mock()
    instance.get_session = Mock(return_value=session)
    engine = Mock()
    engine.dialect.name = engine_type
    migration._modify_columns(
        instance.get_session, engine, "events", ["event_type VARCHAR(64)"]
    )
    if substr:
        assert substr in connection.execute.call_args[0][0].text
    else:
        assert not connection.execute.called


def test_forgiving_add_column(recorder_db_url: str) -> None:
    """Test that add column will continue if column exists."""
    engine = create_engine(recorder_db_url, poolclass=StaticPool)
    with Session(engine) as session:
        session.execute(text("CREATE TABLE hello (id int)"))
        instance = Mock()
        instance.get_session = Mock(return_value=session)
        migration._add_columns(
            instance.get_session, "hello", ["context_id CHARACTER(36)"]
        )
        migration._add_columns(
            instance.get_session, "hello", ["context_id CHARACTER(36)"]
        )
    engine.dispose()


def test_forgiving_add_index(recorder_db_url: str) -> None:
    """Test that add index will continue if index exists."""
    engine = create_engine(recorder_db_url, poolclass=StaticPool)
    db_schema.Base.metadata.create_all(engine)
    with Session(engine) as session:
        instance = Mock()
        instance.get_session = Mock(return_value=session)
        migration._create_index(instance.get_session, "states", "ix_states_context_id")
    engine.dispose()


@pytest.mark.parametrize(
    "exception_type", [OperationalError, ProgrammingError, InternalError]
)
def test_forgiving_add_index_with_other_db_types(
    caplog: pytest.LogCaptureFixture, exception_type
) -> None:
    """Test that add index will continue if index exists on mysql and postgres."""
    mocked_index = Mock()
    type(mocked_index).name = "ix_states_context_id"
    mocked_index.create = Mock(
        side_effect=exception_type(
            "CREATE INDEX ix_states_old_state_id ON states (old_state_id);",
            [],
            'relation "ix_states_old_state_id" already exists',
        )
    )

    mocked_table = Mock()
    type(mocked_table).indexes = PropertyMock(return_value=[mocked_index])

    with patch(
        "homeassistant.components.recorder.migration.Table", return_value=mocked_table
    ):
        migration._create_index(Mock(), "states", "ix_states_context_id")

    assert "already exists on states" in caplog.text
    assert "continuing" in caplog.text


class MockPyODBCProgrammingError(Exception):
    """A mock pyodbc error."""


def test_raise_if_exception_missing_str() -> None:
    """Test we raise an exception if strings are not present."""
    programming_exc = ProgrammingError("select * from;", Mock(), Mock())
    programming_exc.__cause__ = MockPyODBCProgrammingError(
        "[42S11] [FreeTDS][SQL Server]The operation failed because an index or statistics with name 'ix_states_old_state_id' already exists on table 'states'. (1913) (SQLExecDirectW)"
    )

    migration.raise_if_exception_missing_str(
        programming_exc, ["already exists", "duplicate"]
    )

    with pytest.raises(ProgrammingError):
        migration.raise_if_exception_missing_str(programming_exc, ["not present"])


def test_raise_if_exception_missing_empty_cause_str() -> None:
    """Test we raise an exception if strings are not present with an empty cause."""
    programming_exc = ProgrammingError("select * from;", Mock(), Mock())
    programming_exc.__cause__ = MockPyODBCProgrammingError()

    with pytest.raises(ProgrammingError):
        migration.raise_if_exception_missing_str(
            programming_exc, ["already exists", "duplicate"]
        )

    with pytest.raises(ProgrammingError):
        migration.raise_if_exception_missing_str(programming_exc, ["not present"])
