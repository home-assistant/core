"""The tests for the Recorder component."""
# pylint: disable=protected-access
import datetime
import sqlite3
from unittest.mock import ANY, Mock, PropertyMock, call, patch

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
from homeassistant.components import recorder
from homeassistant.components.recorder import RecorderRuns, migration, models
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.models import States
from homeassistant.components.recorder.util import session_scope
import homeassistant.util.dt as dt_util

from .common import async_wait_recording_done_without_instance

from tests.common import async_fire_time_changed, async_mock_service
from tests.components.recorder import models_original


def _get_native_states(hass, entity_id):
    with session_scope(hass=hass) as session:
        return [
            state.to_native()
            for state in session.query(States).filter(States.entity_id == entity_id)
        ]


def create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    engine = create_engine(*args, **kwargs)
    models_original.Base.metadata.create_all(engine)
    return engine


async def test_schema_update_calls(hass):
    """Test that schema migrations occur in correct order."""
    assert await recorder.async_migration_in_progress(hass) is False
    await async_setup_component(hass, "persistent_notification", {})
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

    assert await recorder.async_migration_in_progress(hass) is False
    update.assert_has_calls(
        [
            call(hass.data[DATA_INSTANCE].engine, ANY, version + 1, 0)
            for version in range(0, models.SCHEMA_VERSION)
        ]
    )


async def test_migration_in_progress(hass):
    """Test that we can check for migration in progress."""
    assert await recorder.async_migration_in_progress(hass) is False
    await async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ):
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        await hass.data[DATA_INSTANCE].async_migration_event.wait()
        assert await recorder.async_migration_in_progress(hass) is True
        await async_wait_recording_done_without_instance(hass)

    assert await recorder.async_migration_in_progress(hass) is False


async def test_database_migration_failed(hass):
    """Test we notify if the migration fails."""
    await async_setup_component(hass, "persistent_notification", {})
    create_calls = async_mock_service(hass, "persistent_notification", "create")
    dismiss_calls = async_mock_service(hass, "persistent_notification", "dismiss")
    assert await recorder.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ), patch(
        "homeassistant.components.recorder.migration._apply_update",
        side_effect=ValueError,
    ):
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        await hass.async_add_executor_job(hass.data[DATA_INSTANCE].join)
        await hass.async_block_till_done()

    assert await recorder.async_migration_in_progress(hass) is False
    assert len(create_calls) == 2
    assert len(dismiss_calls) == 1


async def test_database_migration_encounters_corruption(hass):
    """Test we move away the database if its corrupt."""
    await async_setup_component(hass, "persistent_notification", {})
    assert await recorder.async_migration_in_progress(hass) is False

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

    assert await recorder.async_migration_in_progress(hass) is False
    assert move_away.called


async def test_database_migration_encounters_corruption_not_sqlite(hass):
    """Test we fail on database error when we cannot recover."""
    await async_setup_component(hass, "persistent_notification", {})
    create_calls = async_mock_service(hass, "persistent_notification", "create")
    dismiss_calls = async_mock_service(hass, "persistent_notification", "dismiss")
    assert await recorder.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.migration.schema_is_current",
        side_effect=[False, True],
    ), patch(
        "homeassistant.components.recorder.migration.migrate_schema",
        side_effect=DatabaseError("statement", {}, []),
    ), patch(
        "homeassistant.components.recorder.move_away_broken_database"
    ) as move_away:
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        hass.states.async_set("my.entity", "on", {})
        hass.states.async_set("my.entity", "off", {})
        await hass.async_block_till_done()
        await hass.async_add_executor_job(hass.data[DATA_INSTANCE].join)
        await hass.async_block_till_done()

    assert await recorder.async_migration_in_progress(hass) is False
    assert not move_away.called
    assert len(create_calls) == 2
    assert len(dismiss_calls) == 1


async def test_events_during_migration_are_queued(hass):
    """Test that events during migration are queued."""

    assert await recorder.async_migration_in_progress(hass) is False
    await async_setup_component(hass, "persistent_notification", {})
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

    assert await recorder.async_migration_in_progress(hass) is False
    db_states = await hass.async_add_executor_job(_get_native_states, hass, "my.entity")
    assert len(db_states) == 2


async def test_events_during_migration_queue_exhausted(hass):
    """Test that events during migration takes so long the queue is exhausted."""
    await async_setup_component(hass, "persistent_notification", {})
    assert await recorder.async_migration_in_progress(hass) is False

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

    assert await recorder.async_migration_in_progress(hass) is False
    db_states = await hass.async_add_executor_job(_get_native_states, hass, "my.entity")
    assert len(db_states) == 1
    hass.states.async_set("my.entity", "on", {})
    await async_wait_recording_done_without_instance(hass)
    db_states = await hass.async_add_executor_job(_get_native_states, hass, "my.entity")
    assert len(db_states) == 2


async def test_schema_migrate(hass):
    """Test the full schema migration logic.

    We're just testing that the logic can execute successfully here without
    throwing exceptions. Maintaining a set of assertions based on schema
    inspection could quickly become quite cumbersome.
    """

    await async_setup_component(hass, "persistent_notification", {})

    def _mock_setup_run(self):
        self.run_info = RecorderRuns(
            start=self.recording_start, created=dt_util.utcnow()
        )

    with patch("sqlalchemy.create_engine", new=create_engine_test), patch(
        "homeassistant.components.recorder.Recorder._setup_run",
        side_effect=_mock_setup_run,
        autospec=True,
    ) as setup_run:
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
        await hass.async_block_till_done()
        assert setup_run.called


def test_invalid_update():
    """Test that an invalid new version raises an exception."""
    with pytest.raises(ValueError):
        migration._apply_update(Mock(), Mock(), -1, 0)


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
    engine = Mock()
    engine.dialect.name = engine_type
    migration._modify_columns(connection, engine, "events", ["event_type VARCHAR(64)"])
    if substr:
        assert substr in connection.execute.call_args[0][0].text
    else:
        assert not connection.execute.called


def test_forgiving_add_column():
    """Test that add column will continue if column exists."""
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with Session(engine) as session:
        session.execute(text("CREATE TABLE hello (id int)"))
        migration._add_columns(session, "hello", ["context_id CHARACTER(36)"])
        migration._add_columns(session, "hello", ["context_id CHARACTER(36)"])


def test_forgiving_add_index():
    """Test that add index will continue if index exists."""
    engine = create_engine("sqlite://", poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    with Session(engine) as session:
        migration._create_index(session, "states", "ix_states_context_id")


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
