"""The tests for recorder platform migrating data from v30."""
import asyncio
from datetime import timedelta
import importlib
from pathlib import Path
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import SQLITE_URL_PREFIX, core, statistics
from homeassistant.components.recorder.queries import select_event_type_ids
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import EVENT_STATE_CHANGED, Event, EventOrigin, State
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import async_wait_recording_done

from tests.common import async_test_home_assistant

ORIG_TZ = dt_util.DEFAULT_TIME_ZONE

CREATE_ENGINE_TARGET = "homeassistant.components.recorder.core.create_engine"
SCHEMA_MODULE = "tests.components.recorder.db_schema_32"


def _create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    importlib.import_module(SCHEMA_MODULE)
    old_db_schema = sys.modules[SCHEMA_MODULE]
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


async def test_migrate_times(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    """Test we can migrate times."""
    test_dir = tmp_path.joinpath("sqlite")
    test_dir.mkdir()
    test_db_file = test_dir.joinpath("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    importlib.import_module(SCHEMA_MODULE)
    old_db_schema = sys.modules[SCHEMA_MODULE]
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
        time_fired=now,
    )
    custom_event = Event(
        "custom_event",
        {"entity_id": "sensor.custom"},
        EventOrigin.local,
        time_fired=now,
    )
    number_of_migrations = 5

    def _get_states_index_names():
        with session_scope(hass=hass) as session:
            return inspect(session.connection()).get_indexes("states")

    with patch.object(recorder, "db_schema", old_db_schema), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
    ), patch.object(core, "StatesMeta", old_db_schema.StatesMeta), patch.object(
        core, "EventTypes", old_db_schema.EventTypes
    ), patch.object(
        core, "EventData", old_db_schema.EventData
    ), patch.object(
        core, "States", old_db_schema.States
    ), patch.object(
        core, "Events", old_db_schema.Events
    ), patch(
        CREATE_ENGINE_TARGET, new=_create_engine_test
    ), patch(
        "homeassistant.components.recorder.Recorder._migrate_events_context_ids",
    ), patch(
        "homeassistant.components.recorder.Recorder._migrate_states_context_ids",
    ), patch(
        "homeassistant.components.recorder.Recorder._migrate_event_type_ids",
    ), patch(
        "homeassistant.components.recorder.Recorder._migrate_entity_ids",
    ), patch(
        "homeassistant.components.recorder.Recorder._post_migrate_entity_ids"
    ), patch(
        "homeassistant.components.recorder.Recorder._cleanup_legacy_states_event_ids"
    ):
        hass = await async_test_home_assistant(asyncio.get_running_loop())
        recorder_helper.async_initialize_recorder(hass)
        assert await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": dburl}}
        )
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
        await async_wait_recording_done(hass)

        def _add_data():
            with session_scope(hass=hass) as session:
                session.add(old_db_schema.Events.from_event(custom_event))
                session.add(old_db_schema.States.from_event(state_changed_event))

        await recorder.get_instance(hass).async_add_executor_job(_add_data)
        await hass.async_block_till_done()
        await recorder.get_instance(hass).async_block_till_done()

        states_indexes = await recorder.get_instance(hass).async_add_executor_job(
            _get_states_index_names
        )
        states_index_names = {index["name"] for index in states_indexes}
        assert recorder.get_instance(hass).use_legacy_events_index is True

        await hass.async_stop()
        await hass.async_block_till_done()

        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    assert "ix_states_event_id" in states_index_names

    # Test that the duplicates are removed during migration from schema 23
    hass = await async_test_home_assistant(asyncio.get_running_loop())
    recorder_helper.async_initialize_recorder(hass)
    assert await async_setup_component(
        hass, "recorder", {"recorder": {"db_url": dburl}}
    )
    await hass.async_block_till_done()

    # We need to wait for all the migration tasks to complete
    # before we can check the database.
    for _ in range(number_of_migrations):
        await recorder.get_instance(hass).async_block_till_done()
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

    events_result, states_result = await recorder.get_instance(
        hass
    ).async_add_executor_job(_get_test_data_from_db)

    assert len(events_result) == 1
    assert events_result[0].time_fired_ts == now_timestamp
    assert len(states_result) == 1
    assert states_result[0].last_changed_ts == one_second_past_timestamp
    assert states_result[0].last_updated_ts == now_timestamp

    def _get_events_index_names():
        with session_scope(hass=hass) as session:
            return inspect(session.connection()).get_indexes("events")

    events_indexes = await recorder.get_instance(hass).async_add_executor_job(
        _get_events_index_names
    )
    events_index_names = {index["name"] for index in events_indexes}

    assert "ix_events_context_id_bin" in events_index_names
    assert "ix_events_context_id" not in events_index_names

    states_indexes = await recorder.get_instance(hass).async_add_executor_job(
        _get_states_index_names
    )
    states_index_names = {index["name"] for index in states_indexes}

    # sqlite does not support dropping foreign keys so the
    # ix_states_event_id index is not dropped in this case
    # but use_legacy_events_index is still False
    assert "ix_states_event_id" in states_index_names

    assert recorder.get_instance(hass).use_legacy_events_index is False

    await hass.async_stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ


async def test_migrate_can_resume_entity_id_post_migration(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test we resume the entity id post migration after a restart."""
    test_dir = tmp_path.joinpath("sqlite")
    test_dir.mkdir()
    test_db_file = test_dir.joinpath("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    importlib.import_module(SCHEMA_MODULE)
    old_db_schema = sys.modules[SCHEMA_MODULE]
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
        time_fired=now,
    )
    custom_event = Event(
        "custom_event",
        {"entity_id": "sensor.custom"},
        EventOrigin.local,
        time_fired=now,
    )
    number_of_migrations = 5

    def _get_states_index_names():
        with session_scope(hass=hass) as session:
            return inspect(session.connection()).get_indexes("states")

    with patch.object(recorder, "db_schema", old_db_schema), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
    ), patch.object(core, "StatesMeta", old_db_schema.StatesMeta), patch.object(
        core, "EventTypes", old_db_schema.EventTypes
    ), patch.object(
        core, "EventData", old_db_schema.EventData
    ), patch.object(
        core, "States", old_db_schema.States
    ), patch.object(
        core, "Events", old_db_schema.Events
    ), patch(
        CREATE_ENGINE_TARGET, new=_create_engine_test
    ), patch(
        "homeassistant.components.recorder.Recorder._migrate_events_context_ids",
    ), patch(
        "homeassistant.components.recorder.Recorder._migrate_states_context_ids",
    ), patch(
        "homeassistant.components.recorder.Recorder._migrate_event_type_ids",
    ), patch(
        "homeassistant.components.recorder.Recorder._migrate_entity_ids",
    ), patch(
        "homeassistant.components.recorder.Recorder._post_migrate_entity_ids"
    ), patch(
        "homeassistant.components.recorder.Recorder._cleanup_legacy_states_event_ids"
    ):
        hass = await async_test_home_assistant(asyncio.get_running_loop())
        recorder_helper.async_initialize_recorder(hass)
        assert await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": dburl}}
        )
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
        await async_wait_recording_done(hass)

        def _add_data():
            with session_scope(hass=hass) as session:
                session.add(old_db_schema.Events.from_event(custom_event))
                session.add(old_db_schema.States.from_event(state_changed_event))

        await recorder.get_instance(hass).async_add_executor_job(_add_data)
        await hass.async_block_till_done()
        await recorder.get_instance(hass).async_block_till_done()

        states_indexes = await recorder.get_instance(hass).async_add_executor_job(
            _get_states_index_names
        )
        states_index_names = {index["name"] for index in states_indexes}
        assert recorder.get_instance(hass).use_legacy_events_index is True

        await hass.async_stop()
        await hass.async_block_till_done()

    assert "ix_states_event_id" in states_index_names
    assert "ix_states_entity_id_last_updated_ts" in states_index_names

    with patch("homeassistant.components.recorder.Recorder._post_migrate_entity_ids"):
        hass = await async_test_home_assistant(asyncio.get_running_loop())
        recorder_helper.async_initialize_recorder(hass)
        assert await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": dburl}}
        )
        await hass.async_block_till_done()

        # We need to wait for all the migration tasks to complete
        # before we can check the database.
        for _ in range(number_of_migrations):
            await recorder.get_instance(hass).async_block_till_done()
            await async_wait_recording_done(hass)

        states_indexes = await recorder.get_instance(hass).async_add_executor_job(
            _get_states_index_names
        )
        states_index_names = {index["name"] for index in states_indexes}
        await hass.async_stop()
        await hass.async_block_till_done()

    assert "ix_states_entity_id_last_updated_ts" in states_index_names

    hass = await async_test_home_assistant(asyncio.get_running_loop())
    recorder_helper.async_initialize_recorder(hass)
    assert await async_setup_component(
        hass, "recorder", {"recorder": {"db_url": dburl}}
    )
    await hass.async_block_till_done()

    # We need to wait for all the migration tasks to complete
    # before we can check the database.
    for _ in range(number_of_migrations):
        await recorder.get_instance(hass).async_block_till_done()
        await async_wait_recording_done(hass)

    states_indexes = await recorder.get_instance(hass).async_add_executor_job(
        _get_states_index_names
    )
    states_index_names = {index["name"] for index in states_indexes}
    assert "ix_states_entity_id_last_updated_ts" not in states_index_names

    await hass.async_stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ
