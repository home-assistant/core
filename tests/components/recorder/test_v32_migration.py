"""The tests for recorder platform migrating data from v30."""

from collections.abc import Callable
from datetime import timedelta
import importlib
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import core, migration, statistics
from homeassistant.components.recorder.queries import select_event_type_ids
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, EventOrigin, State
import homeassistant.util.dt as dt_util

from .common import async_wait_recording_done
from .conftest import instrument_migration

from tests.common import async_test_home_assistant
from tests.typing import RecorderInstanceGenerator

CREATE_ENGINE_TARGET = "homeassistant.components.recorder.core.create_engine"
SCHEMA_MODULE_30 = "tests.components.recorder.db_schema_30"
SCHEMA_MODULE_32 = "tests.components.recorder.db_schema_32"


def _create_engine_test(schema_module: str) -> Callable:
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """

    def _create_engine_test(*args, **kwargs):
        """Test version of create_engine that initializes with old schema.

        This simulates an existing db with the old schema.
        """
        importlib.import_module(schema_module)
        old_db_schema = sys.modules[schema_module]
        engine = create_engine(*args, **kwargs)
        old_db_schema.Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                recorder.db_schema.StatisticsRuns(start=statistics.get_start_time())
            )
            session.add(
                recorder.db_schema.SchemaChanges(
                    schema_version=old_db_schema.SCHEMA_VERSION
                )
            )
            session.commit()
        return engine

    return _create_engine_test


@pytest.mark.parametrize("enable_migrate_event_context_ids", [True])
@pytest.mark.parametrize("enable_migrate_state_context_ids", [True])
@pytest.mark.parametrize("enable_migrate_event_type_ids", [True])
@pytest.mark.parametrize("enable_migrate_entity_ids", [True])
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
async def test_migrate_times(
    async_test_recorder: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we can migrate times in the events and states tables."""
    importlib.import_module(SCHEMA_MODULE_30)
    old_db_schema = sys.modules[SCHEMA_MODULE_30]
    now = dt_util.utcnow()
    one_second_past = now - timedelta(seconds=1)
    now_timestamp = now.timestamp()
    one_second_past_timestamp = one_second_past.timestamp()

    mock_state = State(
        "sensor.test",
        "old",
        {"last_reset": now.isoformat()},
        last_changed=one_second_past,
        last_updated=now,
    )
    state_changed_event = Event(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.test",
            "old_state": None,
            "new_state": mock_state,
        },
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    custom_event = Event(
        "custom_event",
        {"entity_id": "sensor.custom"},
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    number_of_migrations = 5

    def _get_states_index_names():
        with session_scope(hass=hass) as session:
            return inspect(session.connection()).get_indexes("states")

    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION),
        patch.object(migration, "post_migrate_entity_ids", return_value=False),
        patch.object(migration.EventsContextIDMigration, "migrate_data"),
        patch.object(migration.StatesContextIDMigration, "migrate_data"),
        patch.object(migration.EventTypeIDMigration, "migrate_data"),
        patch.object(migration.EntityIDMigration, "migrate_data"),
        patch.object(migration.EventIDPostMigration, "migrate_data"),
        patch.object(core, "StatesMeta", old_db_schema.StatesMeta),
        patch.object(core, "EventTypes", old_db_schema.EventTypes),
        patch.object(core, "EventData", old_db_schema.EventData),
        patch.object(core, "States", old_db_schema.States),
        patch.object(core, "Events", old_db_schema.Events),
        patch(CREATE_ENGINE_TARGET, new=_create_engine_test(SCHEMA_MODULE_30)),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass) as instance,
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await async_wait_recording_done(hass)

            def _add_data():
                with session_scope(hass=hass) as session:
                    session.add(old_db_schema.Events.from_event(custom_event))
                    session.add(old_db_schema.States.from_event(state_changed_event))

            await instance.async_add_executor_job(_add_data)
            await hass.async_block_till_done()
            await instance.async_block_till_done()

            states_indexes = await instance.async_add_executor_job(
                _get_states_index_names
            )
            states_index_names = {index["name"] for index in states_indexes}
            assert instance.use_legacy_events_index is True

            await hass.async_stop()
            await hass.async_block_till_done()

    assert "ix_states_event_id" in states_index_names

    # Test that the duplicates are removed during migration from schema 23
    async with (
        async_test_home_assistant() as hass,
        async_test_recorder(hass) as instance,
    ):
        await hass.async_block_till_done()

        # We need to wait for all the migration tasks to complete
        # before we can check the database.
        for _ in range(number_of_migrations):
            await instance.async_block_till_done()
            await async_wait_recording_done(hass)

        def _get_test_data_from_db():
            with session_scope(hass=hass) as session:
                events_result = list(
                    session.query(recorder.db_schema.Events).filter(
                        recorder.db_schema.Events.event_type_id.in_(
                            select_event_type_ids(("custom_event",))
                        )
                    )
                )
                states_result = list(
                    session.query(recorder.db_schema.States)
                    .join(
                        recorder.db_schema.StatesMeta,
                        recorder.db_schema.States.metadata_id
                        == recorder.db_schema.StatesMeta.metadata_id,
                    )
                    .where(recorder.db_schema.StatesMeta.entity_id == "sensor.test")
                )
                session.expunge_all()
                return events_result, states_result

        events_result, states_result = await instance.async_add_executor_job(
            _get_test_data_from_db
        )

        assert len(events_result) == 1
        assert events_result[0].time_fired_ts == now_timestamp
        assert events_result[0].time_fired is None
        assert len(states_result) == 1
        assert states_result[0].last_changed_ts == one_second_past_timestamp
        assert states_result[0].last_updated_ts == now_timestamp
        assert states_result[0].last_changed is None
        assert states_result[0].last_updated is None

        def _get_events_index_names():
            with session_scope(hass=hass) as session:
                return inspect(session.connection()).get_indexes("events")

        events_indexes = await instance.async_add_executor_job(_get_events_index_names)
        events_index_names = {index["name"] for index in events_indexes}

        assert "ix_events_context_id_bin" in events_index_names
        assert "ix_events_context_id" not in events_index_names

        states_indexes = await instance.async_add_executor_job(_get_states_index_names)
        states_index_names = {index["name"] for index in states_indexes}

        # sqlite does not support dropping foreign keys so we had to
        # create a new table and copy the data over
        assert "ix_states_event_id" not in states_index_names

        assert instance.use_legacy_events_index is False

        await hass.async_stop()


@pytest.mark.parametrize("enable_migrate_entity_ids", [True])
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
async def test_migrate_can_resume_entity_id_post_migration(
    async_test_recorder: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    recorder_db_url: str,
) -> None:
    """Test we resume the entity id post migration after a restart."""
    importlib.import_module(SCHEMA_MODULE_32)
    old_db_schema = sys.modules[SCHEMA_MODULE_32]
    now = dt_util.utcnow()
    one_second_past = now - timedelta(seconds=1)
    mock_state = State(
        "sensor.test",
        "old",
        {"last_reset": now.isoformat()},
        last_changed=one_second_past,
        last_updated=now,
    )
    state_changed_event = Event(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.test",
            "old_state": None,
            "new_state": mock_state,
        },
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    custom_event = Event(
        "custom_event",
        {"entity_id": "sensor.custom"},
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    number_of_migrations = 5

    def _get_states_index_names():
        with session_scope(hass=hass) as session:
            return inspect(session.connection()).get_indexes("states")

    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION),
        patch.object(migration.EventIDPostMigration, "migrate_data"),
        patch.object(migration, "post_migrate_entity_ids", return_value=False),
        patch.object(core, "StatesMeta", old_db_schema.StatesMeta),
        patch.object(core, "EventTypes", old_db_schema.EventTypes),
        patch.object(core, "EventData", old_db_schema.EventData),
        patch.object(core, "States", old_db_schema.States),
        patch.object(core, "Events", old_db_schema.Events),
        patch(CREATE_ENGINE_TARGET, new=_create_engine_test(SCHEMA_MODULE_32)),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass) as instance,
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await async_wait_recording_done(hass)

            def _add_data():
                with session_scope(hass=hass) as session:
                    session.add(old_db_schema.Events.from_event(custom_event))
                    session.add(old_db_schema.States.from_event(state_changed_event))

            await instance.async_add_executor_job(_add_data)
            await hass.async_block_till_done()
            await instance.async_block_till_done()

            states_indexes = await instance.async_add_executor_job(
                _get_states_index_names
            )
            states_index_names = {index["name"] for index in states_indexes}
            assert instance.use_legacy_events_index is True

            await hass.async_stop()
            await hass.async_block_till_done()

    assert "ix_states_event_id" in states_index_names
    assert "ix_states_entity_id_last_updated_ts" in states_index_names

    async with (
        async_test_home_assistant() as hass,
        async_test_recorder(hass) as instance,
    ):
        await hass.async_block_till_done()

        # We need to wait for all the migration tasks to complete
        # before we can check the database.
        for _ in range(number_of_migrations):
            await instance.async_block_till_done()
            await async_wait_recording_done(hass)

        states_indexes = await instance.async_add_executor_job(_get_states_index_names)
        states_index_names = {index["name"] for index in states_indexes}
        assert "ix_states_entity_id_last_updated_ts" not in states_index_names
        assert "ix_states_event_id" not in states_index_names

        await hass.async_stop()


@pytest.mark.parametrize("enable_migrate_entity_ids", [True])
@pytest.mark.parametrize("enable_migrate_event_ids", [True])
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
async def test_migrate_can_resume_ix_states_event_id_removed(
    async_test_recorder: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    recorder_db_url: str,
) -> None:
    """Test we resume the entity id post migration after a restart.

    This case tests the migration still happens if
    ix_states_event_id is removed from the states table.
    """
    importlib.import_module(SCHEMA_MODULE_32)
    old_db_schema = sys.modules[SCHEMA_MODULE_32]
    now = dt_util.utcnow()
    one_second_past = now - timedelta(seconds=1)
    mock_state = State(
        "sensor.test",
        "old",
        {"last_reset": now.isoformat()},
        last_changed=one_second_past,
        last_updated=now,
    )
    state_changed_event = Event(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.test",
            "old_state": None,
            "new_state": mock_state,
        },
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    custom_event = Event(
        "custom_event",
        {"entity_id": "sensor.custom"},
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    number_of_migrations = 5

    def _get_event_id_foreign_keys():
        assert instance.engine is not None
        return next(
            (
                fk  # type: ignore[misc]
                for fk in inspect(instance.engine).get_foreign_keys("states")
                if fk["constrained_columns"] == ["event_id"]
            ),
            None,
        )

    def _get_states_index_names():
        with session_scope(hass=hass) as session:
            return inspect(session.connection()).get_indexes("states")

    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION),
        patch.object(migration.EventIDPostMigration, "migrate_data"),
        patch.object(migration, "post_migrate_entity_ids", return_value=False),
        patch.object(core, "StatesMeta", old_db_schema.StatesMeta),
        patch.object(core, "EventTypes", old_db_schema.EventTypes),
        patch.object(core, "EventData", old_db_schema.EventData),
        patch.object(core, "States", old_db_schema.States),
        patch.object(core, "Events", old_db_schema.Events),
        patch(CREATE_ENGINE_TARGET, new=_create_engine_test(SCHEMA_MODULE_32)),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass) as instance,
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await async_wait_recording_done(hass)

            def _add_data():
                with session_scope(hass=hass) as session:
                    session.add(old_db_schema.Events.from_event(custom_event))
                    session.add(old_db_schema.States.from_event(state_changed_event))

            await instance.async_add_executor_job(_add_data)
            await hass.async_block_till_done()
            await instance.async_block_till_done()

            await instance.async_add_executor_job(
                migration._drop_index,
                instance.get_session,
                "states",
                "ix_states_event_id",
            )

            states_indexes = await instance.async_add_executor_job(
                _get_states_index_names
            )
            states_index_names = {index["name"] for index in states_indexes}
            assert instance.use_legacy_events_index is True
            assert (
                await instance.async_add_executor_job(_get_event_id_foreign_keys)
                is not None
            )

            await hass.async_stop()
            await hass.async_block_till_done()

    assert "ix_states_entity_id_last_updated_ts" in states_index_names

    async with (
        async_test_home_assistant() as hass,
        async_test_recorder(hass) as instance,
    ):
        await hass.async_block_till_done()

        # We need to wait for all the migration tasks to complete
        # before we can check the database.
        for _ in range(number_of_migrations):
            await instance.async_block_till_done()
            await async_wait_recording_done(hass)

        states_indexes = await instance.async_add_executor_job(_get_states_index_names)
        states_index_names = {index["name"] for index in states_indexes}
        assert instance.use_legacy_events_index is False
        assert "ix_states_entity_id_last_updated_ts" not in states_index_names
        assert "ix_states_event_id" not in states_index_names
        assert await instance.async_add_executor_job(_get_event_id_foreign_keys) is None

        await hass.async_stop()


@pytest.mark.usefixtures("skip_by_db_engine")
@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.parametrize("enable_migrate_event_ids", [True])
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
async def test_out_of_disk_space_while_rebuild_states_table(
    async_test_recorder: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    recorder_db_url: str,
) -> None:
    """Test that we can recover from out of disk space while rebuilding the states table.

    This case tests the migration still happens if
    ix_states_event_id is removed from the states table.
    """
    importlib.import_module(SCHEMA_MODULE_32)
    old_db_schema = sys.modules[SCHEMA_MODULE_32]
    now = dt_util.utcnow()
    one_second_past = now - timedelta(seconds=1)
    mock_state = State(
        "sensor.test",
        "old",
        {"last_reset": now.isoformat()},
        last_changed=one_second_past,
        last_updated=now,
    )
    state_changed_event = Event(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.test",
            "old_state": None,
            "new_state": mock_state,
        },
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    custom_event = Event(
        "custom_event",
        {"entity_id": "sensor.custom"},
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    number_of_migrations = 5

    def _get_event_id_foreign_keys():
        assert instance.engine is not None
        return next(
            (
                fk  # type: ignore[misc]
                for fk in inspect(instance.engine).get_foreign_keys("states")
                if fk["constrained_columns"] == ["event_id"]
            ),
            None,
        )

    def _get_states_index_names():
        with session_scope(hass=hass) as session:
            return inspect(session.connection()).get_indexes("states")

    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION),
        patch.object(migration.EventIDPostMigration, "migrate_data"),
        patch.object(migration, "post_migrate_entity_ids", return_value=False),
        patch.object(core, "StatesMeta", old_db_schema.StatesMeta),
        patch.object(core, "EventTypes", old_db_schema.EventTypes),
        patch.object(core, "EventData", old_db_schema.EventData),
        patch.object(core, "States", old_db_schema.States),
        patch.object(core, "Events", old_db_schema.Events),
        patch(CREATE_ENGINE_TARGET, new=_create_engine_test(SCHEMA_MODULE_32)),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass) as instance,
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await async_wait_recording_done(hass)

            def _add_data():
                with session_scope(hass=hass) as session:
                    session.add(old_db_schema.Events.from_event(custom_event))
                    session.add(old_db_schema.States.from_event(state_changed_event))

            await instance.async_add_executor_job(_add_data)
            await hass.async_block_till_done()
            await instance.async_block_till_done()

            await instance.async_add_executor_job(
                migration._drop_index,
                instance.get_session,
                "states",
                "ix_states_event_id",
            )

            states_indexes = await instance.async_add_executor_job(
                _get_states_index_names
            )
            states_index_names = {index["name"] for index in states_indexes}
            assert instance.use_legacy_events_index is True
            assert (
                await instance.async_add_executor_job(_get_event_id_foreign_keys)
                is not None
            )

            await hass.async_stop()
            await hass.async_block_till_done()

    assert "ix_states_entity_id_last_updated_ts" in states_index_names

    # Simulate out of disk space while rebuilding the states table by
    # - patching CreateTable to raise SQLAlchemyError for SQLite
    # - patching DropConstraint to raise InternalError for MySQL and PostgreSQL
    with (
        patch(
            "homeassistant.components.recorder.migration.CreateTable",
            side_effect=SQLAlchemyError,
        ),
        patch(
            "homeassistant.components.recorder.migration.DropConstraint",
            side_effect=OperationalError(
                None, None, OSError("No space left on device")
            ),
        ),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass) as instance,
        ):
            await hass.async_block_till_done()

            # We need to wait for all the migration tasks to complete
            # before we can check the database.
            for _ in range(number_of_migrations):
                await instance.async_block_till_done()
                await async_wait_recording_done(hass)

            states_indexes = await instance.async_add_executor_job(
                _get_states_index_names
            )
            states_index_names = {index["name"] for index in states_indexes}
            assert instance.use_legacy_events_index is True
            assert "Error recreating SQLite table states" in caplog.text
            assert await instance.async_add_executor_job(_get_event_id_foreign_keys)

            await hass.async_stop()

    # Now run it again to verify the table rebuild tries again
    caplog.clear()
    async with (
        async_test_home_assistant() as hass,
        async_test_recorder(hass) as instance,
    ):
        await hass.async_block_till_done()

        # We need to wait for all the migration tasks to complete
        # before we can check the database.
        for _ in range(number_of_migrations):
            await instance.async_block_till_done()
            await async_wait_recording_done(hass)

        states_indexes = await instance.async_add_executor_job(_get_states_index_names)
        states_index_names = {index["name"] for index in states_indexes}
        assert instance.use_legacy_events_index is False
        assert "ix_states_entity_id_last_updated_ts" not in states_index_names
        assert "ix_states_event_id" not in states_index_names
        assert "Rebuilding SQLite table states finished" in caplog.text
        assert await instance.async_add_executor_job(_get_event_id_foreign_keys) is None

        await hass.async_stop()


@pytest.mark.usefixtures("skip_by_db_engine")
@pytest.mark.skip_on_db_engine(["sqlite"])
@pytest.mark.parametrize("enable_migrate_entity_ids", [True])
@pytest.mark.parametrize("enable_migrate_event_ids", [True])
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
async def test_out_of_disk_space_while_removing_foreign_key(
    async_test_recorder: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    recorder_db_url: str,
) -> None:
    """Test that we can recover from out of disk space while removing the foreign key.

    This case tests the migration still happens if
    ix_states_event_id is removed from the states table.

    Note that the test is somewhat forced; the states.event_id foreign key constraint is
    removed when migrating to schema version 46, inspecting the schema in
    EventIDPostMigration.migrate_data, is not likely to fail.
    """
    importlib.import_module(SCHEMA_MODULE_32)
    old_db_schema = sys.modules[SCHEMA_MODULE_32]
    now = dt_util.utcnow()
    one_second_past = now - timedelta(seconds=1)
    mock_state = State(
        "sensor.test",
        "old",
        {"last_reset": now.isoformat()},
        last_changed=one_second_past,
        last_updated=now,
    )
    state_changed_event = Event(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.test",
            "old_state": None,
            "new_state": mock_state,
        },
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    custom_event = Event(
        "custom_event",
        {"entity_id": "sensor.custom"},
        EventOrigin.local,
        time_fired_timestamp=now.timestamp(),
    )
    number_of_migrations = 5

    def _get_event_id_foreign_keys():
        assert instance.engine is not None
        return next(
            (
                fk  # type: ignore[misc]
                for fk in inspect(instance.engine).get_foreign_keys("states")
                if fk["constrained_columns"] == ["event_id"]
            ),
            None,
        )

    def _get_states_index_names():
        with session_scope(hass=hass) as session:
            return inspect(session.connection()).get_indexes("states")

    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION),
        patch.object(migration.EventIDPostMigration, "migrate_data"),
        patch.object(migration, "post_migrate_entity_ids", return_value=False),
        patch.object(core, "StatesMeta", old_db_schema.StatesMeta),
        patch.object(core, "EventTypes", old_db_schema.EventTypes),
        patch.object(core, "EventData", old_db_schema.EventData),
        patch.object(core, "States", old_db_schema.States),
        patch.object(core, "Events", old_db_schema.Events),
        patch(CREATE_ENGINE_TARGET, new=_create_engine_test(SCHEMA_MODULE_32)),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass) as instance,
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await async_wait_recording_done(hass)

            def _add_data():
                with session_scope(hass=hass) as session:
                    session.add(old_db_schema.Events.from_event(custom_event))
                    session.add(old_db_schema.States.from_event(state_changed_event))

            await instance.async_add_executor_job(_add_data)
            await hass.async_block_till_done()
            await instance.async_block_till_done()

            await instance.async_add_executor_job(
                migration._drop_index,
                instance.get_session,
                "states",
                "ix_states_event_id",
            )

            states_indexes = await instance.async_add_executor_job(
                _get_states_index_names
            )
            states_index_names = {index["name"] for index in states_indexes}
            assert instance.use_legacy_events_index is True
            assert (
                await instance.async_add_executor_job(_get_event_id_foreign_keys)
                is not None
            )

            await hass.async_stop()
            await hass.async_block_till_done()

    assert "ix_states_entity_id_last_updated_ts" in states_index_names

    async with async_test_home_assistant() as hass:
        with instrument_migration(hass) as instrumented_migration:
            # Allow migration to start, but stall when live migration is completed
            instrumented_migration.migration_stall.set()
            instrumented_migration.live_migration_done_stall.clear()

            async with async_test_recorder(hass, wait_recorder=False) as instance:
                await hass.async_block_till_done()

                # Wait for live migration to complete
                await hass.async_add_executor_job(
                    instrumented_migration.live_migration_done.wait
                )

                # Simulate out of disk space while removing the foreign key from the states table by
                # - patching DropConstraint to raise InternalError for MySQL and PostgreSQL
                with (
                    patch(
                        "homeassistant.components.recorder.migration.sqlalchemy.inspect",
                        side_effect=OperationalError(
                            None, None, OSError("No space left on device")
                        ),
                    ),
                ):
                    instrumented_migration.live_migration_done_stall.set()
                    # We need to wait for all the migration tasks to complete
                    # before we can check the database.
                    for _ in range(number_of_migrations):
                        await instance.async_block_till_done()
                        await async_wait_recording_done(hass)

                    states_indexes = await instance.async_add_executor_job(
                        _get_states_index_names
                    )
                    states_index_names = {index["name"] for index in states_indexes}
                    assert instance.use_legacy_events_index is True
                    # The states.event_id foreign key constraint was removed when
                    # migration to schema version 46
                    assert (
                        await instance.async_add_executor_job(
                            _get_event_id_foreign_keys
                        )
                        is None
                    )

                    await hass.async_stop()

    # Now run it again to verify the table rebuild tries again
    caplog.clear()
    async with (
        async_test_home_assistant() as hass,
        async_test_recorder(hass) as instance,
    ):
        await hass.async_block_till_done()

        # We need to wait for all the migration tasks to complete
        # before we can check the database.
        for _ in range(number_of_migrations):
            await instance.async_block_till_done()
            await async_wait_recording_done(hass)

        states_indexes = await instance.async_add_executor_job(_get_states_index_names)
        states_index_names = {index["name"] for index in states_indexes}
        assert instance.use_legacy_events_index is False
        assert "ix_states_entity_id_last_updated_ts" not in states_index_names
        assert "ix_states_event_id" not in states_index_names
        assert await instance.async_add_executor_job(_get_event_id_foreign_keys) is None

        await hass.async_stop()
