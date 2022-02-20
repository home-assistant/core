"""The tests for the Recorder component."""
# pylint: disable=protected-access
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
from homeassistant.components.recorder import RecorderRuns, migration, models
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.models import States
from homeassistant.components.recorder.util import session_scope
import homeassistant.util.dt as dt_util

from .common import async_wait_recording_done_without_instance, create_engine_test

from tests.common import async_fire_time_changed


def _get_native_states(hass, entity_id):
    with session_scope(hass=hass) as session:
        return [
            state.to_native()
            for state in session.query(States).filter(States.entity_id == entity_id)
        ]


async def test_schema_update_calls(hass):
    """Test that schema migrations occur in correct order."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ), patch(
        "homeassistant.components.recorder.migration._apply_update",
        wraps=migration._apply_update,
    ) as update:
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        await async_wait_recording_done_without_instance(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    update.assert_has_calls(
        [
            call(hass.data[DATA_INSTANCE], version + 1, 0)
            for version in range(0, models.SCHEMA_VERSION)
        ]
    )


async def test_migration_in_progress(hass):
    """Test that we can check for migration in progress."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ):
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        await hass.data[DATA_INSTANCE].async_migration_event.wait()
        assert recorder.util.async_migration_in_progress(hass) is True
        await async_wait_recording_done_without_instance(hass)

    assert recorder.util.async_migration_in_progress(hass) is False


async def test_database_migration_failed(hass):
    """Test we notify if the migration fails."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ), patch(
        "homeassistant.components.recorder.migration._apply_update",
        side_effect=ValueError,
    ), patch(
        "homeassistant.components.persistent_notification.create", side_effect=pn.create
    ) as mock_create, patch(
        "homeassistant.components.persistent_notification.dismiss",
        side_effect=pn.dismiss,
    ) as mock_dismiss:
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        await hass.async_add_executor_job(hass.data[DATA_INSTANCE].join)
        await hass.async_block_till_done()

    assert recorder.util.async_migration_in_progress(hass) is False
    assert len(mock_create.mock_calls) == 2
    assert len(mock_dismiss.mock_calls) == 1


async def test_database_migration_encounters_corruption(hass):
    """Test we move away the database if its corrupt."""

    assert recorder.util.async_migration_in_progress(hass) is False

    sqlite3_exception = DatabaseError("statement", {}, [])
    sqlite3_exception.__cause__ = sqlite3.DatabaseError()

    with patch(
        "homeassistant.components.recorder.migration.schema_is_current",
        side_effect=[False, True],
    ), patch(
        "homeassistant.components.recorder.migration.migrate_schema",
        side_effect=sqlite3_exception,
    ), patch(
        "homeassistant.components.recorder.move_away_broken_database"
    ) as move_away:
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await async_wait_recording_done_without_instance(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    assert move_away.called


async def test_database_migration_encounters_corruption_not_sqlite(hass):
    """Test we fail on database error when we cannot recover."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.migration.schema_is_current",
        side_effect=[False, True],
    ), patch(
        "homeassistant.components.recorder.migration.migrate_schema",
        side_effect=DatabaseError("statement", {}, []),
    ), patch(
        "homeassistant.components.recorder.move_away_broken_database"
    ) as move_away, patch(
        "homeassistant.components.persistent_notification.create", side_effect=pn.create
    ) as mock_create, patch(
        "homeassistant.components.persistent_notification.dismiss",
        side_effect=pn.dismiss,
    ) as mock_dismiss:
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        await hass.async_add_executor_job(hass.data[DATA_INSTANCE].join)
        await hass.async_block_till_done()

    assert recorder.util.async_migration_in_progress(hass) is False
    assert not move_away.called
    assert len(mock_create.mock_calls) == 2
    assert len(mock_dismiss.mock_calls) == 1


async def test_events_during_migration_are_queued(hass):
    """Test that events during migration are queued."""

    assert recorder.util.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ):
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=2))
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=4))
        await hass.data[DATA_INSTANCE].async_recorder_ready.wait()
        await async_wait_recording_done_without_instance(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    db_states = await hass.async_add_executor_job(_get_native_states, hass, "my.entity")
    assert len(db_states) == 2


async def test_events_during_migration_queue_exhausted(hass):
    """Test that events during migration takes so long the queue is exhausted."""

    assert recorder.util.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ), patch.object(recorder, "MAX_QUEUE_BACKLOG", 1):
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        hass.states.async_set("my.entity", "on", {})
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=2))
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=4))
        await hass.async_block_till_done()
        hass.states.async_set("my.entity", "off", {})
        await hass.data[DATA_INSTANCE].async_recorder_ready.wait()
        await async_wait_recording_done_without_instance(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    db_states = await hass.async_add_executor_job(_get_native_states, hass, "my.entity")
    assert len(db_states) == 1
    hass.states.async_set("my.entity", "on", {})
    await async_wait_recording_done_without_instance(hass)
    db_states = await hass.async_add_executor_job(_get_native_states, hass, "my.entity")
    assert len(db_states) == 2


@pytest.mark.parametrize("start_version", [0, 16, 18, 22])
async def test_schema_migrate(hass, start_version):
    """Test the full schema migration logic.

    We're just testing that the logic can execute successfully here without
    throwing exceptions. Maintaining a set of assertions based on schema
    inspection could quickly become quite cumbersome.
    """

    migration_done = threading.Event()
    migration_stall = threading.Event()
    migration_version = None
    real_migration = recorder.migration.migrate_schema

    def _create_engine_test(*args, **kwargs):
        """Test version of create_engine that initializes with old schema.

        This simulates an existing db with the old schema.
        """
        module = f"tests.components.recorder.models_schema_{str(start_version)}"
        importlib.import_module(module)
        old_models = sys.modules[module]
        engine = create_engine(*args, **kwargs)
        old_models.Base.metadata.create_all(engine)
        if start_version > 0:
            with Session(engine) as session:
                session.add(recorder.models.SchemaChanges(schema_version=start_version))
                session.commit()
        return engine

    def _mock_setup_run(self):
        self.run_info = RecorderRuns(
            start=self.recording_start, created=dt_util.utcnow()
        )

    def _instrument_migration(*args):
        """Control migration progress and check results."""
        nonlocal migration_done
        nonlocal migration_version
        nonlocal migration_stall
        migration_stall.wait()
        try:
            real_migration(*args)
        except Exception:
            migration_done.set()
            raise

        # Check and report the outcome of the migration; if migration fails
        # the recorder will silently create a new database.
        with session_scope(hass=hass) as session:
            res = (
                session.query(models.SchemaChanges)
                .order_by(models.SchemaChanges.change_id.desc())
                .first()
            )
            migration_version = res.schema_version
        migration_done.set()

    with patch(
        "homeassistant.components.recorder.create_engine", new=_create_engine_test
    ), patch(
        "homeassistant.components.recorder.Recorder._setup_run",
        side_effect=_mock_setup_run,
        autospec=True,
    ) as setup_run, patch(
        "homeassistant.components.recorder.migration.migrate_schema",
        wraps=_instrument_migration,
    ):
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        assert recorder.util.async_migration_in_progress(hass) is True
        migration_stall.set()
        await hass.async_block_till_done()
        migration_done.wait()
        await async_wait_recording_done_without_instance(hass)
        assert migration_version == models.SCHEMA_VERSION
        assert setup_run.called
        assert recorder.util.async_migration_in_progress(hass) is not True


def test_invalid_update():
    """Test that an invalid new version raises an exception."""
    with pytest.raises(ValueError):
        migration._apply_update(Mock(), -1, 0)


@pytest.mark.parametrize(
    ["engine_type", "substr"],
    [
        ("postgresql", "ALTER event_type TYPE VARCHAR(64)"),
        ("mssql", "ALTER COLUMN event_type VARCHAR(64)"),
        ("mysql", "MODIFY event_type VARCHAR(64)"),
        ("sqlite", None),
    ],
)
def test_modify_column(engine_type, substr):
    """Test that modify column generates the expected query."""
    connection = Mock()
    session = Mock()
    session.connection = Mock(return_value=connection)
    instance = Mock()
    instance.get_session = Mock(return_value=session)
    engine = Mock()
    engine.dialect.name = engine_type
    migration._modify_columns(instance, engine, "events", ["event_type VARCHAR(64)"])
    if substr:
        assert substr in connection.execute.call_args[0][0].text
    else:
        assert not connection.execute.called


def test_forgiving_add_column():
    """Test that add column will continue if column exists."""
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with Session(engine) as session:
        session.execute(text("CREATE TABLE hello (id int)"))
        instance = Mock()
        instance.get_session = Mock(return_value=session)
        migration._add_columns(instance, "hello", ["context_id CHARACTER(36)"])
        migration._add_columns(instance, "hello", ["context_id CHARACTER(36)"])


def test_forgiving_add_index():
    """Test that add index will continue if index exists."""
    engine = create_engine("sqlite://", poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    with Session(engine) as session:
        instance = Mock()
        instance.get_session = Mock(return_value=session)
        migration._create_index(instance, "states", "ix_states_context_id")


@pytest.mark.parametrize(
    "exception_type", [OperationalError, ProgrammingError, InternalError]
)
def test_forgiving_add_index_with_other_db_types(caplog, exception_type):
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


def test_raise_if_exception_missing_str():
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


def test_raise_if_exception_missing_empty_cause_str():
    """Test we raise an exception if strings are not present with an empty cause."""
    programming_exc = ProgrammingError("select * from;", Mock(), Mock())
    programming_exc.__cause__ = MockPyODBCProgrammingError()

    with pytest.raises(ProgrammingError):
        migration.raise_if_exception_missing_str(
            programming_exc, ["already exists", "duplicate"]
        )

    with pytest.raises(ProgrammingError):
        migration.raise_if_exception_missing_str(programming_exc, ["not present"])
