"""The tests for the Recorder component."""

import datetime
import importlib
import sqlite3
import sys
from unittest.mock import Mock, PropertyMock, call, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import (
    DatabaseError,
    InternalError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from homeassistant.components import persistent_notification as pn, recorder
from homeassistant.components.recorder import db_schema, migration
from homeassistant.components.recorder.db_schema import (
    SCHEMA_VERSION,
    Events,
    RecorderRuns,
    States,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
import homeassistant.util.dt as dt_util

from .common import async_wait_recording_done, create_engine_test
from .conftest import InstrumentedMigration

from tests.common import async_fire_time_changed
from tests.typing import RecorderInstanceGenerator


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceGenerator,
) -> None:
    """Set up recorder."""


def _get_native_states(hass, entity_id):
    with session_scope(hass=hass, read_only=True) as session:
        instance = recorder.get_instance(hass)
        metadata_id = instance.states_meta_manager.get(entity_id, session, True)
        states = []
        for dbstate in session.query(States).filter(States.metadata_id == metadata_id):
            dbstate.entity_id = entity_id
            states.append(dbstate.to_native())
        return states


async def test_schema_update_calls(
    hass: HomeAssistant, async_setup_recorder_instance: RecorderInstanceGenerator
) -> None:
    """Test that schema migrations occur in correct order."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with (
        patch(
            "homeassistant.components.recorder.core.create_engine",
            new=create_engine_test,
        ),
        patch(
            "homeassistant.components.recorder.migration._apply_update",
            wraps=migration._apply_update,
        ) as update,
    ):
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    instance = recorder.get_instance(hass)
    engine = instance.engine
    session_maker = instance.get_session
    update.assert_has_calls(
        [
            call(instance, hass, engine, session_maker, version + 1, 0)
            for version in range(db_schema.SCHEMA_VERSION)
        ]
    )


async def test_migration_in_progress(
    hass: HomeAssistant,
    recorder_db_url: str,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    instrument_migration: InstrumentedMigration,
) -> None:
    """Test that we can check for migration in progress."""
    if recorder_db_url.startswith("mysql://"):
        # The database drop at the end of this test currently hangs on MySQL
        # because the post migration is still in progress in the background
        # which results in a deadlock in InnoDB. This behavior is not likely
        # to happen in real life because the database does not get dropped
        # in normal operation.
        return

    assert recorder.util.async_migration_in_progress(hass) is False

    with (
        patch(
            "homeassistant.components.recorder.core.create_engine",
            new=create_engine_test,
        ),
    ):
        await async_setup_recorder_instance(hass, wait_recorder=False)
        await hass.async_add_executor_job(instrument_migration.migration_started.wait)
        assert recorder.util.async_migration_in_progress(hass) is True

        # Let migration finish
        instrument_migration.migration_stall.set()
        await async_wait_recording_done(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    assert recorder.get_instance(hass).schema_version == SCHEMA_VERSION


async def test_database_migration_failed(
    hass: HomeAssistant, async_setup_recorder_instance: RecorderInstanceGenerator
) -> None:
    """Test we notify if the migration fails."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with (
        patch(
            "homeassistant.components.recorder.core.create_engine",
            new=create_engine_test,
        ),
        patch(
            "homeassistant.components.recorder.migration._apply_update",
            side_effect=ValueError,
        ),
        patch(
            "homeassistant.components.persistent_notification.create",
            side_effect=pn.create,
        ) as mock_create,
        patch(
            "homeassistant.components.persistent_notification.dismiss",
            side_effect=pn.dismiss,
        ) as mock_dismiss,
    ):
        await async_setup_recorder_instance(hass, wait_recorder=False)
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        await hass.async_add_executor_job(recorder.get_instance(hass).join)
        await hass.async_block_till_done()

    assert recorder.util.async_migration_in_progress(hass) is False
    assert len(mock_create.mock_calls) == 2
    assert len(mock_dismiss.mock_calls) == 1


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
async def test_database_migration_encounters_corruption(
    hass: HomeAssistant,
    recorder_db_url: str,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test we move away the database if its corrupt.

    This test is specific for SQLite, wiping the database on error only happens
    with SQLite.
    """

    assert recorder.util.async_migration_in_progress(hass) is False

    sqlite3_exception = DatabaseError("statement", {}, [])
    sqlite3_exception.__cause__ = sqlite3.DatabaseError()

    with (
        patch(
            "homeassistant.components.recorder.migration._schema_is_current",
            side_effect=[False],
        ),
        patch(
            "homeassistant.components.recorder.migration.migrate_schema",
            side_effect=sqlite3_exception,
        ),
        patch(
            "homeassistant.components.recorder.core.move_away_broken_database"
        ) as move_away,
    ):
        await async_setup_recorder_instance(hass)
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await async_wait_recording_done(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    assert move_away.called


async def test_database_migration_encounters_corruption_not_sqlite(
    hass: HomeAssistant, async_setup_recorder_instance: RecorderInstanceGenerator
) -> None:
    """Test we fail on database error when we cannot recover."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with (
        patch(
            "homeassistant.components.recorder.migration._schema_is_current",
            side_effect=[False],
        ),
        patch(
            "homeassistant.components.recorder.migration.migrate_schema",
            side_effect=DatabaseError("statement", {}, []),
        ),
        patch(
            "homeassistant.components.recorder.core.move_away_broken_database"
        ) as move_away,
        patch(
            "homeassistant.components.persistent_notification.create",
            side_effect=pn.create,
        ) as mock_create,
        patch(
            "homeassistant.components.persistent_notification.dismiss",
            side_effect=pn.dismiss,
        ) as mock_dismiss,
    ):
        await async_setup_recorder_instance(hass, wait_recorder=False)
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
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    instrument_migration: InstrumentedMigration,
) -> None:
    """Test that events during migration are queued."""

    assert recorder.util.async_migration_in_progress(hass) is False

    with (
        patch(
            "homeassistant.components.recorder.core.create_engine",
            new=create_engine_test,
        ),
    ):
        await async_setup_recorder_instance(
            hass, {"commit_interval": 0}, wait_recorder=False
        )
        await hass.async_add_executor_job(instrument_migration.migration_started.wait)
        assert recorder.util.async_migration_in_progress(hass) is True
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=2))
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=4))

        # Let migration finish
        instrument_migration.migration_stall.set()
        await recorder.get_instance(hass).async_recorder_ready.wait()
        await async_wait_recording_done(hass)

    assert recorder.util.async_migration_in_progress(hass) is False
    db_states = await recorder.get_instance(hass).async_add_executor_job(
        _get_native_states, hass, "my.entity"
    )
    assert len(db_states) == 2


async def test_events_during_migration_queue_exhausted(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    instrument_migration: InstrumentedMigration,
) -> None:
    """Test that events during migration takes so long the queue is exhausted."""

    assert recorder.util.async_migration_in_progress(hass) is False

    with (
        patch(
            "homeassistant.components.recorder.core.create_engine",
            new=create_engine_test,
        ),
        patch.object(recorder.core, "MAX_QUEUE_BACKLOG_MIN_VALUE", 1),
        patch.object(
            recorder.core, "MIN_AVAILABLE_MEMORY_FOR_QUEUE_BACKLOG", sys.maxsize
        ),
    ):
        await async_setup_recorder_instance(
            hass, {"commit_interval": 0}, wait_recorder=False
        )
        await hass.async_add_executor_job(instrument_migration.migration_started.wait)
        assert recorder.util.async_migration_in_progress(hass) is True
        hass.states.async_set("my.entity", "on", {})
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=2))
        await hass.async_block_till_done()
        async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=4))
        await hass.async_block_till_done()
        hass.states.async_set("my.entity", "off", {})

        # Let migration finish
        instrument_migration.migration_stall.set()
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
    [(0, True), (16, True), (18, True), (22, True), (25, True), (43, True)],
)
async def test_schema_migrate(
    hass: HomeAssistant,
    recorder_db_url: str,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    instrument_migration: InstrumentedMigration,
    start_version,
    live,
) -> None:
    """Test the full schema migration logic.

    We're just testing that the logic can execute successfully here without
    throwing exceptions. Maintaining a set of assertions based on schema
    inspection could quickly become quite cumbersome.
    """

    real_create_index = recorder.migration._create_index
    create_calls = 0

    def _create_engine_test(*args, **kwargs):
        """Test version of create_engine that initializes with old schema.

        This simulates an existing db with the old schema.
        """
        module = f"tests.components.recorder.db_schema_{start_version!s}"
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
            start=self.recorder_runs_manager.recording_start, created=dt_util.utcnow()
        )

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

    with (
        patch(
            "homeassistant.components.recorder.core.create_engine",
            new=_create_engine_test,
        ),
        patch(
            "homeassistant.components.recorder.Recorder._setup_run",
            side_effect=_mock_setup_run,
            autospec=True,
        ) as setup_run,
        patch("homeassistant.components.recorder.util.time.sleep"),
        patch(
            "homeassistant.components.recorder.migration._create_index",
            wraps=_sometimes_failing_create_index,
        ),
        patch(
            "homeassistant.components.recorder.Recorder._process_state_changed_event_into_session",
        ),
        patch(
            "homeassistant.components.recorder.Recorder._process_non_state_changed_event_into_session",
        ),
        patch(
            "homeassistant.components.recorder.Recorder._pre_process_startup_events",
        ),
    ):
        await async_setup_recorder_instance(hass, wait_recorder=False)
        await hass.async_add_executor_job(instrument_migration.migration_started.wait)
        assert recorder.util.async_migration_in_progress(hass) is True
        await recorder_helper.async_wait_recorder(hass)

        assert recorder.util.async_migration_in_progress(hass) is True
        assert recorder.util.async_migration_is_live(hass) == live
        instrument_migration.migration_stall.set()
        await hass.async_block_till_done()
        await hass.async_add_executor_job(instrument_migration.migration_done.wait)
        await async_wait_recording_done(hass)
        assert instrument_migration.migration_version == db_schema.SCHEMA_VERSION
        assert setup_run.called
        assert recorder.util.async_migration_in_progress(hass) is not True
        assert instrument_migration.apply_update_mock.called


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
        migration._create_index(
            instance.get_session, "states", "ix_states_context_id_bin"
        )
    engine.dispose()


def test_forgiving_drop_index(
    recorder_db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that drop index will continue if index drop fails."""
    engine = create_engine(recorder_db_url, poolclass=StaticPool)
    db_schema.Base.metadata.create_all(engine)
    with Session(engine) as session:
        instance = Mock()
        instance.get_session = Mock(return_value=session)
        migration._drop_index(
            instance.get_session, "states", "ix_states_context_id_bin"
        )
        migration._drop_index(
            instance.get_session, "states", "ix_states_context_id_bin"
        )

        with (
            patch(
                "homeassistant.components.recorder.migration.get_index_by_name",
                return_value="ix_states_context_id_bin",
            ),
            patch.object(
                session, "connection", side_effect=SQLAlchemyError("connection failure")
            ),
        ):
            migration._drop_index(
                instance.get_session, "states", "ix_states_context_id_bin"
            )
        assert "Failed to drop index" in caplog.text
        assert "connection failure" in caplog.text
        caplog.clear()
        with (
            patch(
                "homeassistant.components.recorder.migration.get_index_by_name",
                return_value="ix_states_context_id_bin",
            ),
            patch.object(
                session, "connection", side_effect=SQLAlchemyError("connection failure")
            ),
        ):
            migration._drop_index(
                instance.get_session, "states", "ix_states_context_id_bin", quiet=True
            )
        assert "Failed to drop index" not in caplog.text
        assert "connection failure" not in caplog.text
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


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
def test_rebuild_sqlite_states_table(recorder_db_url: str) -> None:
    """Test that we can rebuild the states table in SQLite.

    This test is specific for SQLite.
    """
    engine = create_engine(recorder_db_url)
    session_maker = scoped_session(sessionmaker(bind=engine, future=True))
    with session_scope(session=session_maker()) as session:
        db_schema.Base.metadata.create_all(engine)
    with session_scope(session=session_maker()) as session:
        session.add(States(state="on"))
        session.commit()

    migration.rebuild_sqlite_table(session_maker, engine, States)

    with session_scope(session=session_maker()) as session:
        assert session.query(States).count() == 1
        assert session.query(States).first().state == "on"

    engine.dispose()


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
def test_rebuild_sqlite_states_table_missing_fails(
    recorder_db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling missing states table when attempting rebuild.

    This test is specific for SQLite.
    """
    engine = create_engine(recorder_db_url)
    session_maker = scoped_session(sessionmaker(bind=engine, future=True))
    with session_scope(session=session_maker()) as session:
        db_schema.Base.metadata.create_all(engine)

    with session_scope(session=session_maker()) as session:
        session.add(Events(event_type="state_changed", event_data="{}"))
        session.connection().execute(text("DROP TABLE states"))
        session.commit()

    migration.rebuild_sqlite_table(session_maker, engine, States)
    assert "Error recreating SQLite table states" in caplog.text
    caplog.clear()

    # Now rebuild the events table to make sure the database did not
    # get corrupted
    migration.rebuild_sqlite_table(session_maker, engine, Events)

    with session_scope(session=session_maker()) as session:
        assert session.query(Events).count() == 1
        assert session.query(Events).first().event_type == "state_changed"
        assert session.query(Events).first().event_data == "{}"

    engine.dispose()


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine")
def test_rebuild_sqlite_states_table_extra_columns(
    recorder_db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling extra columns when rebuilding the states table.

    This test is specific for SQLite.
    """
    engine = create_engine(recorder_db_url)
    session_maker = scoped_session(sessionmaker(bind=engine, future=True))
    with session_scope(session=session_maker()) as session:
        db_schema.Base.metadata.create_all(engine)
    with session_scope(session=session_maker()) as session:
        session.add(States(state="on"))
        session.commit()
        session.connection().execute(
            text("ALTER TABLE states ADD COLUMN extra_column TEXT")
        )

    migration.rebuild_sqlite_table(session_maker, engine, States)
    assert "Error recreating SQLite table states" not in caplog.text

    with session_scope(session=session_maker()) as session:
        assert session.query(States).count() == 1
        assert session.query(States).first().state == "on"

    engine.dispose()


def test_restore_foreign_key_constraints_with_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we can drop and then restore foreign keys.

    This is not supported on SQLite
    """

    constraints_to_restore = [
        (
            "events",
            "data_id",
            {
                "comment": None,
                "constrained_columns": ["data_id"],
                "name": "events_data_id_fkey",
                "options": {},
                "referred_columns": ["data_id"],
                "referred_schema": None,
                "referred_table": "event_data",
            },
        ),
    ]

    connection = Mock()
    connection.execute = Mock(side_effect=InternalError(None, None, None))
    session = Mock()
    session.connection = Mock(return_value=connection)
    instance = Mock()
    instance.get_session = Mock(return_value=session)
    engine = Mock()

    session_maker = Mock(return_value=session)
    migration._restore_foreign_key_constraints(
        session_maker, engine, constraints_to_restore
    )

    assert "Could not update foreign options in events table" in caplog.text
