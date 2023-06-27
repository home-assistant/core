"""The tests for the recorder filter matching the EntityFilter component."""
# pylint: disable=invalid-name
import importlib
import sys
from unittest.mock import patch
import uuid

from freezegun import freeze_time
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import core, migration, statistics
from homeassistant.components.recorder.db_schema import (
    Events,
    EventTypes,
    States,
    StatesMeta,
)
from homeassistant.components.recorder.queries import select_event_type_ids
from homeassistant.components.recorder.tasks import (
    EntityIDMigrationTask,
    EntityIDPostMigrationTask,
    EventsContextIDMigrationTask,
    EventTypeIDMigrationTask,
    StatesContextIDMigrationTask,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util
from homeassistant.util.ulid import bytes_to_ulid, ulid_at_time, ulid_to_bytes

from .common import async_recorder_block_till_done, async_wait_recording_done

from tests.typing import RecorderInstanceGenerator

CREATE_ENGINE_TARGET = "homeassistant.components.recorder.core.create_engine"
SCHEMA_MODULE = "tests.components.recorder.db_schema_32"
ORIG_TZ = dt_util.DEFAULT_TIME_ZONE


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


@pytest.fixture(autouse=True)
def db_schema_32():
    """Fixture to initialize the db with the old schema."""
    importlib.import_module(SCHEMA_MODULE)
    old_db_schema = sys.modules[SCHEMA_MODULE]

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
    ), patch.object(
        core, "StateAttributes", old_db_schema.StateAttributes
    ), patch.object(
        core, "EntityIDMigrationTask", core.RecorderTask
    ), patch(
        CREATE_ENGINE_TARGET, new=_create_engine_test
    ):
        yield


@pytest.fixture(name="legacy_recorder_mock")
async def legacy_recorder_mock_fixture(recorder_mock):
    """Fixture for legacy recorder mock."""
    with patch.object(recorder_mock.states_meta_manager, "active", False):
        yield recorder_mock


@pytest.mark.parametrize("enable_migrate_context_ids", [True])
async def test_migrate_events_context_ids(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test we can migrate old uuid context ids and ulid context ids to binary format."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)

    test_uuid = uuid.uuid4()
    uuid_hex = test_uuid.hex
    uuid_bin = test_uuid.bytes

    def _insert_events():
        with session_scope(hass=hass) as session:
            session.add_all(
                (
                    Events(
                        event_type="old_uuid_context_id_event",
                        event_data=None,
                        origin_idx=0,
                        time_fired=None,
                        time_fired_ts=1877721632.452529,
                        context_id=uuid_hex,
                        context_id_bin=None,
                        context_user_id=None,
                        context_user_id_bin=None,
                        context_parent_id=None,
                        context_parent_id_bin=None,
                    ),
                    Events(
                        event_type="empty_context_id_event",
                        event_data=None,
                        origin_idx=0,
                        time_fired=None,
                        time_fired_ts=1877721632.552529,
                        context_id=None,
                        context_id_bin=None,
                        context_user_id=None,
                        context_user_id_bin=None,
                        context_parent_id=None,
                        context_parent_id_bin=None,
                    ),
                    Events(
                        event_type="ulid_context_id_event",
                        event_data=None,
                        origin_idx=0,
                        time_fired=None,
                        time_fired_ts=1877721632.552529,
                        context_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
                        context_id_bin=None,
                        context_user_id="9400facee45711eaa9308bfd3d19e474",
                        context_user_id_bin=None,
                        context_parent_id="01ARZ3NDEKTSV4RRFFQ69G5FA2",
                        context_parent_id_bin=None,
                    ),
                    Events(
                        event_type="invalid_context_id_event",
                        event_data=None,
                        origin_idx=0,
                        time_fired=None,
                        time_fired_ts=1877721632.552529,
                        context_id="invalid",
                        context_id_bin=None,
                        context_user_id=None,
                        context_user_id_bin=None,
                        context_parent_id=None,
                        context_parent_id_bin=None,
                    ),
                    Events(
                        event_type="garbage_context_id_event",
                        event_data=None,
                        origin_idx=0,
                        time_fired=None,
                        time_fired_ts=1277721632.552529,
                        context_id="adapt_lgt:b'5Cf*':interval:b'0R'",
                        context_id_bin=None,
                        context_user_id=None,
                        context_user_id_bin=None,
                        context_parent_id=None,
                        context_parent_id_bin=None,
                    ),
                    Events(
                        event_type="event_with_garbage_context_id_no_time_fired_ts",
                        event_data=None,
                        origin_idx=0,
                        time_fired=None,
                        time_fired_ts=None,
                        context_id="adapt_lgt:b'5Cf*':interval:b'0R'",
                        context_id_bin=None,
                        context_user_id=None,
                        context_user_id_bin=None,
                        context_parent_id=None,
                        context_parent_id_bin=None,
                    ),
                )
            )

    await instance.async_add_executor_job(_insert_events)

    await async_wait_recording_done(hass)
    now = dt_util.utcnow()
    expected_ulid_fallback_start = ulid_to_bytes(ulid_at_time(now.timestamp()))[0:6]
    with freeze_time(now):
        # This is a threadsafe way to add a task to the recorder
        instance.queue_task(EventsContextIDMigrationTask())
        await async_recorder_block_till_done(hass)

    def _object_as_dict(obj):
        return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

    def _fetch_migrated_events():
        with session_scope(hass=hass) as session:
            events = (
                session.query(Events)
                .filter(
                    Events.event_type.in_(
                        [
                            "old_uuid_context_id_event",
                            "empty_context_id_event",
                            "ulid_context_id_event",
                            "invalid_context_id_event",
                            "garbage_context_id_event",
                            "event_with_garbage_context_id_no_time_fired_ts",
                        ]
                    )
                )
                .all()
            )
            assert len(events) == 6
            return {event.event_type: _object_as_dict(event) for event in events}

    events_by_type = await instance.async_add_executor_job(_fetch_migrated_events)

    old_uuid_context_id_event = events_by_type["old_uuid_context_id_event"]
    assert old_uuid_context_id_event["context_id"] is None
    assert old_uuid_context_id_event["context_user_id"] is None
    assert old_uuid_context_id_event["context_parent_id"] is None
    assert old_uuid_context_id_event["context_id_bin"] == uuid_bin
    assert old_uuid_context_id_event["context_user_id_bin"] is None
    assert old_uuid_context_id_event["context_parent_id_bin"] is None

    empty_context_id_event = events_by_type["empty_context_id_event"]
    assert empty_context_id_event["context_id"] is None
    assert empty_context_id_event["context_user_id"] is None
    assert empty_context_id_event["context_parent_id"] is None
    assert empty_context_id_event["context_id_bin"].startswith(
        b"\x01\xb50\xeeO("
    )  # 6 bytes of timestamp + random
    assert empty_context_id_event["context_user_id_bin"] is None
    assert empty_context_id_event["context_parent_id_bin"] is None

    ulid_context_id_event = events_by_type["ulid_context_id_event"]
    assert ulid_context_id_event["context_id"] is None
    assert ulid_context_id_event["context_user_id"] is None
    assert ulid_context_id_event["context_parent_id"] is None
    assert (
        bytes_to_ulid(ulid_context_id_event["context_id_bin"])
        == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    )
    assert (
        ulid_context_id_event["context_user_id_bin"]
        == b"\x94\x00\xfa\xce\xe4W\x11\xea\xa90\x8b\xfd=\x19\xe4t"
    )
    assert (
        bytes_to_ulid(ulid_context_id_event["context_parent_id_bin"])
        == "01ARZ3NDEKTSV4RRFFQ69G5FA2"
    )

    invalid_context_id_event = events_by_type["invalid_context_id_event"]
    assert invalid_context_id_event["context_id"] is None
    assert invalid_context_id_event["context_user_id"] is None
    assert invalid_context_id_event["context_parent_id"] is None
    assert invalid_context_id_event["context_id_bin"].startswith(
        b"\x01\xb50\xeeO("
    )  # 6 bytes of timestamp + random
    assert invalid_context_id_event["context_user_id_bin"] is None
    assert invalid_context_id_event["context_parent_id_bin"] is None

    garbage_context_id_event = events_by_type["garbage_context_id_event"]
    assert garbage_context_id_event["context_id"] is None
    assert garbage_context_id_event["context_user_id"] is None
    assert garbage_context_id_event["context_parent_id"] is None
    assert garbage_context_id_event["context_id_bin"].startswith(
        b"\x01)~$\xdf("
    )  # 6 bytes of timestamp + random
    assert garbage_context_id_event["context_user_id_bin"] is None
    assert garbage_context_id_event["context_parent_id_bin"] is None

    event_with_garbage_context_id_no_time_fired_ts = events_by_type[
        "event_with_garbage_context_id_no_time_fired_ts"
    ]
    assert event_with_garbage_context_id_no_time_fired_ts["context_id"] is None
    assert event_with_garbage_context_id_no_time_fired_ts["context_user_id"] is None
    assert event_with_garbage_context_id_no_time_fired_ts["context_parent_id"] is None
    assert event_with_garbage_context_id_no_time_fired_ts["context_id_bin"].startswith(
        expected_ulid_fallback_start
    )  # 6 bytes of timestamp + random
    assert event_with_garbage_context_id_no_time_fired_ts["context_user_id_bin"] is None
    assert (
        event_with_garbage_context_id_no_time_fired_ts["context_parent_id_bin"] is None
    )


@pytest.mark.parametrize("enable_migrate_context_ids", [True])
async def test_migrate_states_context_ids(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test we can migrate old uuid context ids and ulid context ids to binary format."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)

    test_uuid = uuid.uuid4()
    uuid_hex = test_uuid.hex
    uuid_bin = test_uuid.bytes

    def _insert_states():
        with session_scope(hass=hass) as session:
            session.add_all(
                (
                    States(
                        entity_id="state.old_uuid_context_id",
                        last_updated_ts=1477721632.452529,
                        context_id=uuid_hex,
                        context_id_bin=None,
                        context_user_id=None,
                        context_user_id_bin=None,
                        context_parent_id=None,
                        context_parent_id_bin=None,
                    ),
                    States(
                        entity_id="state.empty_context_id",
                        last_updated_ts=1477721632.552529,
                        context_id=None,
                        context_id_bin=None,
                        context_user_id=None,
                        context_user_id_bin=None,
                        context_parent_id=None,
                        context_parent_id_bin=None,
                    ),
                    States(
                        entity_id="state.ulid_context_id",
                        last_updated_ts=1477721632.552529,
                        context_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
                        context_id_bin=None,
                        context_user_id="9400facee45711eaa9308bfd3d19e474",
                        context_user_id_bin=None,
                        context_parent_id="01ARZ3NDEKTSV4RRFFQ69G5FA2",
                        context_parent_id_bin=None,
                    ),
                    States(
                        entity_id="state.invalid_context_id",
                        last_updated_ts=1477721632.552529,
                        context_id="invalid",
                        context_id_bin=None,
                        context_user_id=None,
                        context_user_id_bin=None,
                        context_parent_id=None,
                        context_parent_id_bin=None,
                    ),
                    States(
                        entity_id="state.garbage_context_id",
                        last_updated_ts=1477721632.552529,
                        context_id="adapt_lgt:b'5Cf*':interval:b'0R'",
                        context_id_bin=None,
                        context_user_id=None,
                        context_user_id_bin=None,
                        context_parent_id=None,
                        context_parent_id_bin=None,
                    ),
                    States(
                        entity_id="state.human_readable_uuid_context_id",
                        last_updated_ts=1477721632.552529,
                        context_id="0ae29799-ee4e-4f45-8116-f582d7d3ee65",
                        context_id_bin=None,
                        context_user_id="0ae29799-ee4e-4f45-8116-f582d7d3ee65",
                        context_user_id_bin=None,
                        context_parent_id="0ae29799-ee4e-4f45-8116-f582d7d3ee65",
                        context_parent_id_bin=None,
                    ),
                )
            )

    await instance.async_add_executor_job(_insert_states)

    await async_wait_recording_done(hass)
    instance.queue_task(StatesContextIDMigrationTask())
    await async_recorder_block_till_done(hass)

    def _object_as_dict(obj):
        return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

    def _fetch_migrated_states():
        with session_scope(hass=hass) as session:
            events = (
                session.query(States)
                .filter(
                    States.entity_id.in_(
                        [
                            "state.old_uuid_context_id",
                            "state.empty_context_id",
                            "state.ulid_context_id",
                            "state.invalid_context_id",
                            "state.garbage_context_id",
                            "state.human_readable_uuid_context_id",
                        ]
                    )
                )
                .all()
            )
            assert len(events) == 6
            return {state.entity_id: _object_as_dict(state) for state in events}

    states_by_entity_id = await instance.async_add_executor_job(_fetch_migrated_states)

    old_uuid_context_id = states_by_entity_id["state.old_uuid_context_id"]
    assert old_uuid_context_id["context_id"] is None
    assert old_uuid_context_id["context_user_id"] is None
    assert old_uuid_context_id["context_parent_id"] is None
    assert old_uuid_context_id["context_id_bin"] == uuid_bin
    assert old_uuid_context_id["context_user_id_bin"] is None
    assert old_uuid_context_id["context_parent_id_bin"] is None

    empty_context_id = states_by_entity_id["state.empty_context_id"]
    assert empty_context_id["context_id"] is None
    assert empty_context_id["context_user_id"] is None
    assert empty_context_id["context_parent_id"] is None
    assert empty_context_id["context_id_bin"].startswith(
        b"\x01X\x0f\x12\xaf("
    )  # 6 bytes of timestamp + random
    assert empty_context_id["context_user_id_bin"] is None
    assert empty_context_id["context_parent_id_bin"] is None

    ulid_context_id = states_by_entity_id["state.ulid_context_id"]
    assert ulid_context_id["context_id"] is None
    assert ulid_context_id["context_user_id"] is None
    assert ulid_context_id["context_parent_id"] is None
    assert (
        bytes_to_ulid(ulid_context_id["context_id_bin"]) == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    )
    assert (
        ulid_context_id["context_user_id_bin"]
        == b"\x94\x00\xfa\xce\xe4W\x11\xea\xa90\x8b\xfd=\x19\xe4t"
    )
    assert (
        bytes_to_ulid(ulid_context_id["context_parent_id_bin"])
        == "01ARZ3NDEKTSV4RRFFQ69G5FA2"
    )

    invalid_context_id = states_by_entity_id["state.invalid_context_id"]
    assert invalid_context_id["context_id"] is None
    assert invalid_context_id["context_user_id"] is None
    assert invalid_context_id["context_parent_id"] is None
    assert invalid_context_id["context_id_bin"].startswith(
        b"\x01X\x0f\x12\xaf("
    )  # 6 bytes of timestamp + random
    assert invalid_context_id["context_user_id_bin"] is None
    assert invalid_context_id["context_parent_id_bin"] is None

    garbage_context_id = states_by_entity_id["state.garbage_context_id"]
    assert garbage_context_id["context_id"] is None
    assert garbage_context_id["context_user_id"] is None
    assert garbage_context_id["context_parent_id"] is None
    assert garbage_context_id["context_id_bin"].startswith(
        b"\x01X\x0f\x12\xaf("
    )  # 6 bytes of timestamp + random
    assert garbage_context_id["context_user_id_bin"] is None
    assert garbage_context_id["context_parent_id_bin"] is None

    human_readable_uuid_context_id = states_by_entity_id[
        "state.human_readable_uuid_context_id"
    ]
    assert human_readable_uuid_context_id["context_id"] is None
    assert human_readable_uuid_context_id["context_user_id"] is None
    assert human_readable_uuid_context_id["context_parent_id"] is None
    assert (
        human_readable_uuid_context_id["context_id_bin"]
        == b"\n\xe2\x97\x99\xeeNOE\x81\x16\xf5\x82\xd7\xd3\xeee"
    )
    assert (
        human_readable_uuid_context_id["context_user_id_bin"]
        == b"\n\xe2\x97\x99\xeeNOE\x81\x16\xf5\x82\xd7\xd3\xeee"
    )
    assert (
        human_readable_uuid_context_id["context_parent_id_bin"]
        == b"\n\xe2\x97\x99\xeeNOE\x81\x16\xf5\x82\xd7\xd3\xeee"
    )


@pytest.mark.parametrize("enable_migrate_event_type_ids", [True])
async def test_migrate_event_type_ids(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test we can migrate event_types to the EventTypes table."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)

    def _insert_events():
        with session_scope(hass=hass) as session:
            session.add_all(
                (
                    Events(
                        event_type="event_type_one",
                        origin_idx=0,
                        time_fired_ts=1677721632.452529,
                    ),
                    Events(
                        event_type="event_type_one",
                        origin_idx=0,
                        time_fired_ts=1677721632.552529,
                    ),
                    Events(
                        event_type="event_type_two",
                        origin_idx=0,
                        time_fired_ts=1677721632.552529,
                    ),
                )
            )

    await instance.async_add_executor_job(_insert_events)

    await async_wait_recording_done(hass)
    # This is a threadsafe way to add a task to the recorder
    instance.queue_task(EventTypeIDMigrationTask())
    await async_recorder_block_till_done(hass)

    def _fetch_migrated_events():
        with session_scope(hass=hass, read_only=True) as session:
            events = (
                session.query(Events.event_id, Events.time_fired, EventTypes.event_type)
                .filter(
                    Events.event_type_id.in_(
                        select_event_type_ids(
                            (
                                "event_type_one",
                                "event_type_two",
                            )
                        )
                    )
                )
                .outerjoin(EventTypes, Events.event_type_id == EventTypes.event_type_id)
                .all()
            )
            assert len(events) == 3
            result = {}
            for event in events:
                result.setdefault(event.event_type, []).append(
                    {
                        "event_id": event.event_id,
                        "time_fired": event.time_fired,
                        "event_type": event.event_type,
                    }
                )
            return result

    events_by_type = await instance.async_add_executor_job(_fetch_migrated_events)
    assert len(events_by_type["event_type_one"]) == 2
    assert len(events_by_type["event_type_two"]) == 1

    def _get_many():
        with session_scope(hass=hass, read_only=True) as session:
            return instance.event_type_manager.get_many(
                ("event_type_one", "event_type_two"), session
            )

    mapped = await instance.async_add_executor_job(_get_many)
    assert mapped["event_type_one"] is not None
    assert mapped["event_type_two"] is not None


@pytest.mark.parametrize("enable_migrate_entity_ids", [True])
async def test_migrate_entity_ids(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test we can migrate entity_ids to the StatesMeta table."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)

    def _insert_states():
        with session_scope(hass=hass) as session:
            session.add_all(
                (
                    States(
                        entity_id="sensor.one",
                        state="one_1",
                        last_updated_ts=1.452529,
                    ),
                    States(
                        entity_id="sensor.two",
                        state="two_2",
                        last_updated_ts=2.252529,
                    ),
                    States(
                        entity_id="sensor.two",
                        state="two_1",
                        last_updated_ts=3.152529,
                    ),
                )
            )

    await instance.async_add_executor_job(_insert_states)

    await async_wait_recording_done(hass)
    # This is a threadsafe way to add a task to the recorder
    instance.queue_task(EntityIDMigrationTask())
    await async_recorder_block_till_done(hass)

    def _fetch_migrated_states():
        with session_scope(hass=hass, read_only=True) as session:
            states = (
                session.query(
                    States.state,
                    States.metadata_id,
                    States.last_updated_ts,
                    StatesMeta.entity_id,
                )
                .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
                .all()
            )
            assert len(states) == 3
            result = {}
            for state in states:
                result.setdefault(state.entity_id, []).append(
                    {
                        "state_id": state.entity_id,
                        "last_updated_ts": state.last_updated_ts,
                        "state": state.state,
                    }
                )
            return result

    states_by_entity_id = await instance.async_add_executor_job(_fetch_migrated_states)
    assert len(states_by_entity_id["sensor.two"]) == 2
    assert len(states_by_entity_id["sensor.one"]) == 1


@pytest.mark.parametrize("enable_migrate_entity_ids", [True])
async def test_post_migrate_entity_ids(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test we can migrate entity_ids to the StatesMeta table."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)

    def _insert_events():
        with session_scope(hass=hass) as session:
            session.add_all(
                (
                    States(
                        entity_id="sensor.one",
                        state="one_1",
                        last_updated_ts=1.452529,
                    ),
                    States(
                        entity_id="sensor.two",
                        state="two_2",
                        last_updated_ts=2.252529,
                    ),
                    States(
                        entity_id="sensor.two",
                        state="two_1",
                        last_updated_ts=3.152529,
                    ),
                )
            )

    await instance.async_add_executor_job(_insert_events)

    await async_wait_recording_done(hass)
    # This is a threadsafe way to add a task to the recorder
    instance.queue_task(EntityIDPostMigrationTask())
    await async_recorder_block_till_done(hass)

    def _fetch_migrated_states():
        with session_scope(hass=hass, read_only=True) as session:
            states = session.query(
                States.state,
                States.entity_id,
            ).all()
            assert len(states) == 3
            return {state.state: state.entity_id for state in states}

    states_by_state = await instance.async_add_executor_job(_fetch_migrated_states)
    assert states_by_state["one_1"] is None
    assert states_by_state["two_2"] is None
    assert states_by_state["two_1"] is None


@pytest.mark.parametrize("enable_migrate_entity_ids", [True])
async def test_migrate_null_entity_ids(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test we can migrate entity_ids to the StatesMeta table."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)

    def _insert_states():
        with session_scope(hass=hass) as session:
            session.add(
                States(
                    entity_id="sensor.one",
                    state="one_1",
                    last_updated_ts=1.452529,
                ),
            )
            session.add_all(
                States(
                    entity_id=None,
                    state="empty",
                    last_updated_ts=time + 1.452529,
                )
                for time in range(1000)
            )
            session.add(
                States(
                    entity_id="sensor.one",
                    state="one_1",
                    last_updated_ts=2.452529,
                ),
            )

    await instance.async_add_executor_job(_insert_states)

    await async_wait_recording_done(hass)
    # This is a threadsafe way to add a task to the recorder
    instance.queue_task(EntityIDMigrationTask())
    await async_recorder_block_till_done(hass)
    await async_recorder_block_till_done(hass)

    def _fetch_migrated_states():
        with session_scope(hass=hass, read_only=True) as session:
            states = (
                session.query(
                    States.state,
                    States.metadata_id,
                    States.last_updated_ts,
                    StatesMeta.entity_id,
                )
                .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
                .all()
            )
            assert len(states) == 1002
            result = {}
            for state in states:
                result.setdefault(state.entity_id, []).append(
                    {
                        "state_id": state.entity_id,
                        "last_updated_ts": state.last_updated_ts,
                        "state": state.state,
                    }
                )
            return result

    states_by_entity_id = await instance.async_add_executor_job(_fetch_migrated_states)
    assert len(states_by_entity_id[migration._EMPTY_ENTITY_ID]) == 1000
    assert len(states_by_entity_id["sensor.one"]) == 2


@pytest.mark.parametrize("enable_migrate_event_type_ids", [True])
async def test_migrate_null_event_type_ids(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test we can migrate event_types to the EventTypes table when the event_type is NULL."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)

    def _insert_events():
        with session_scope(hass=hass) as session:
            session.add(
                Events(
                    event_type="event_type_one",
                    origin_idx=0,
                    time_fired_ts=1.452529,
                ),
            )
            session.add_all(
                Events(
                    event_type=None,
                    origin_idx=0,
                    time_fired_ts=time + 1.452529,
                )
                for time in range(1000)
            )
            session.add(
                Events(
                    event_type="event_type_one",
                    origin_idx=0,
                    time_fired_ts=2.452529,
                ),
            )

    await instance.async_add_executor_job(_insert_events)

    await async_wait_recording_done(hass)
    # This is a threadsafe way to add a task to the recorder

    instance.queue_task(EventTypeIDMigrationTask())
    await async_recorder_block_till_done(hass)
    await async_recorder_block_till_done(hass)

    def _fetch_migrated_events():
        with session_scope(hass=hass, read_only=True) as session:
            events = (
                session.query(Events.event_id, Events.time_fired, EventTypes.event_type)
                .filter(
                    Events.event_type_id.in_(
                        select_event_type_ids(
                            (
                                "event_type_one",
                                migration._EMPTY_EVENT_TYPE,
                            )
                        )
                    )
                )
                .outerjoin(EventTypes, Events.event_type_id == EventTypes.event_type_id)
                .all()
            )
            assert len(events) == 1002
            result = {}
            for event in events:
                result.setdefault(event.event_type, []).append(
                    {
                        "event_id": event.event_id,
                        "time_fired": event.time_fired,
                        "event_type": event.event_type,
                    }
                )
            return result

    events_by_type = await instance.async_add_executor_job(_fetch_migrated_events)
    assert len(events_by_type["event_type_one"]) == 2
    assert len(events_by_type[migration._EMPTY_EVENT_TYPE]) == 1000
