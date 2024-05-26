"""The tests for the Recorder component."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import threading
from typing import cast
from unittest.mock import MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from sqlalchemy.exc import DatabaseError, OperationalError, SQLAlchemyError
from sqlalchemy.pool import QueuePool

from homeassistant.components import recorder
from homeassistant.components.recorder import (
    CONF_AUTO_PURGE,
    CONF_AUTO_REPACK,
    CONF_COMMIT_INTERVAL,
    CONF_DB_MAX_RETRIES,
    CONF_DB_RETRY_WAIT,
    CONF_DB_URL,
    CONFIG_SCHEMA,
    DOMAIN,
    SQLITE_URL_PREFIX,
    Recorder,
    db_schema,
    get_instance,
    migration,
    statistics,
)
from homeassistant.components.recorder.const import (
    EVENT_RECORDER_5MIN_STATISTICS_GENERATED,
    EVENT_RECORDER_HOURLY_STATISTICS_GENERATED,
    KEEPALIVE_TIME,
    SupportedDialect,
)
from homeassistant.components.recorder.db_schema import (
    SCHEMA_VERSION,
    EventData,
    Events,
    EventTypes,
    RecorderRuns,
    StateAttributes,
    States,
    StatesMeta,
    StatisticsRuns,
)
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.components.recorder.queries import select_event_type_ids
from homeassistant.components.recorder.services import (
    SERVICE_DISABLE,
    SERVICE_ENABLE,
    SERVICE_PURGE,
    SERVICE_PURGE_ENTITIES,
)
from homeassistant.components.recorder.table_managers import (
    state_attributes as state_attributes_table_manager,
    states_meta as states_meta_table_manager,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    MATCH_ALL,
    STATE_LOCKED,
    STATE_UNLOCKED,
)
from homeassistant.core import Context, CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import (
    entity_registry as er,
    issue_registry as ir,
    recorder as recorder_helper,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads

from .common import (
    async_block_recorder,
    async_recorder_block_till_done,
    async_wait_recording_done,
    convert_pending_states_to_meta,
    corrupt_db_file,
    run_information_with_session,
)

from tests.common import (
    MockEntity,
    MockEntityPlatform,
    async_fire_time_changed,
    async_test_home_assistant,
    mock_platform,
)
from tests.typing import RecorderInstanceGenerator


@pytest.fixture
async def mock_recorder_before_hass(
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Set up recorder."""


@pytest.fixture
def setup_recorder(recorder_mock: Recorder) -> None:
    """Set up recorder."""


@pytest.fixture
def small_cache_size() -> Generator[None, None, None]:
    """Patch the default cache size to 8."""
    with (
        patch.object(state_attributes_table_manager, "CACHE_SIZE", 8),
        patch.object(states_meta_table_manager, "CACHE_SIZE", 8),
    ):
        yield


def _default_recorder(hass):
    """Return a recorder with reasonable defaults."""
    return Recorder(
        hass,
        auto_purge=True,
        auto_repack=True,
        keep_days=7,
        commit_interval=1,
        uri="sqlite://",
        db_max_retries=10,
        db_retry_wait=3,
        entity_filter=CONFIG_SCHEMA({DOMAIN: {}}),
        exclude_event_types=set(),
    )


async def test_shutdown_before_startup_finishes(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    recorder_db_url: str,
    tmp_path: Path,
) -> None:
    """Test shutdown before recorder starts is clean."""
    if recorder_db_url == "sqlite://":
        # On-disk database because this test does not play nice with the
        # MutexPool
        recorder_db_url = "sqlite:///" + str(tmp_path / "pytest.db")
    config = {
        recorder.CONF_DB_URL: recorder_db_url,
        recorder.CONF_COMMIT_INTERVAL: 1,
    }
    hass.set_state(CoreState.not_running)

    recorder_helper.async_initialize_recorder(hass)
    hass.async_create_task(async_setup_recorder_instance(hass, config))
    await recorder_helper.async_wait_recorder(hass)
    instance = get_instance(hass)

    session = await instance.async_add_executor_job(instance.get_session)

    with patch.object(instance, "engine"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
        await hass.async_block_till_done()
        await hass.async_stop()

    def _run_information_with_session():
        instance.recorder_and_worker_thread_ids.add(threading.get_ident())
        return run_information_with_session(session)

    run_info = await instance.async_add_executor_job(_run_information_with_session)

    assert run_info.run_id == 1
    assert run_info.start is not None
    assert run_info.end is not None
    # We patched out engine to prevent the close from happening
    # so we need to manually close the session
    session.close()
    await hass.async_add_executor_job(instance._shutdown)


async def test_canceled_before_startup_finishes(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test recorder shuts down when its startup future is canceled out from under it."""
    hass.set_state(CoreState.not_running)
    recorder_helper.async_initialize_recorder(hass)
    hass.async_create_task(async_setup_recorder_instance(hass))
    await recorder_helper.async_wait_recorder(hass)

    instance = get_instance(hass)
    instance._hass_started.cancel()
    with patch.object(instance, "engine"):
        await hass.async_block_till_done()
        await hass.async_add_executor_job(instance.join)
    assert (
        "Recorder startup was externally canceled before it could complete"
        in caplog.text
    )
    # We patched out engine to prevent the close from happening
    # so we need to manually close the session
    await hass.async_add_executor_job(instance._shutdown)


async def test_shutdown_closes_connections(
    hass: HomeAssistant, setup_recorder: None
) -> None:
    """Test shutdown closes connections."""

    hass.set_state(CoreState.not_running)

    instance = recorder.get_instance(hass)
    await instance.async_db_ready
    await hass.async_block_till_done()
    pool = instance.engine.pool
    pool.shutdown = Mock()

    def _ensure_connected():
        with session_scope(hass=hass, read_only=True) as session:
            list(session.query(States))

    await instance.async_add_executor_job(_ensure_connected)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()

    assert len(pool.shutdown.mock_calls) == 1
    with pytest.raises(RuntimeError):
        assert instance.get_session()


async def test_state_gets_saved_when_set_before_start_event(
    hass: HomeAssistant, async_setup_recorder_instance: RecorderInstanceGenerator
) -> None:
    """Test we can record an event when starting with not running."""

    hass.set_state(CoreState.not_running)

    recorder_helper.async_initialize_recorder(hass)
    hass.async_create_task(async_setup_recorder_instance(hass))
    await recorder_helper.async_wait_recorder(hass)

    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.async_set(entity_id, state, attributes)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 1
        assert db_states[0].event_id is None


async def test_saving_state(hass: HomeAssistant, setup_recorder: None) -> None:
    """Test saving and restoring a state."""
    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.async_set(entity_id, state, attributes)

    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        db_states = []
        for db_state, db_state_attributes, states_meta in (
            session.query(States, StateAttributes, StatesMeta)
            .outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            )
            .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
        ):
            db_state.entity_id = states_meta.entity_id
            db_states.append(db_state)
            state = db_state.to_native()
            state.attributes = db_state_attributes.to_native()
        assert len(db_states) == 1
        assert db_states[0].event_id is None

    assert state.as_dict() == _state_with_context(hass, entity_id).as_dict()


@pytest.mark.parametrize(
    ("dialect_name", "expected_attributes"),
    [
        (SupportedDialect.MYSQL, {"test_attr": 5, "test_attr_10": "silly\0stuff"}),
        (SupportedDialect.POSTGRESQL, {"test_attr": 5, "test_attr_10": "silly"}),
        (SupportedDialect.SQLITE, {"test_attr": 5, "test_attr_10": "silly\0stuff"}),
    ],
)
async def test_saving_state_with_nul(
    hass: HomeAssistant, setup_recorder: None, dialect_name, expected_attributes
) -> None:
    """Test saving and restoring a state with nul in attributes."""
    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "silly\0stuff"}

    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", dialect_name
    ):
        hass.states.async_set(entity_id, state, attributes)
        await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        db_states = []
        for db_state, db_state_attributes, states_meta in (
            session.query(States, StateAttributes, StatesMeta)
            .outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            )
            .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
        ):
            db_state.entity_id = states_meta.entity_id
            db_states.append(db_state)
            state = db_state.to_native()
            state.attributes = db_state_attributes.to_native()
        assert len(db_states) == 1
        assert db_states[0].event_id is None

    expected = _state_with_context(hass, entity_id)
    expected.attributes = expected_attributes
    assert state.as_dict() == expected.as_dict()


async def test_saving_many_states(
    hass: HomeAssistant, async_setup_recorder_instance: RecorderInstanceGenerator
) -> None:
    """Test we expire after many commits."""
    instance = await async_setup_recorder_instance(
        hass, {recorder.CONF_COMMIT_INTERVAL: 0}
    )

    entity_id = "test.recorder"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    with (
        patch.object(instance.event_session, "expire_all") as expire_all,
        patch.object(recorder.core, "EXPIRE_AFTER_COMMITS", 2),
    ):
        for _ in range(3):
            hass.states.async_set(entity_id, "on", attributes)
            await async_wait_recording_done(hass)
            hass.states.async_set(entity_id, "off", attributes)
            await async_wait_recording_done(hass)

    assert expire_all.called

    with session_scope(hass=hass, read_only=True) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 6
        assert db_states[0].event_id is None


async def test_saving_state_with_intermixed_time_changes(
    hass: HomeAssistant, setup_recorder: None
) -> None:
    """Test saving states with intermixed time changes."""
    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}
    attributes2 = {"test_attr": 10, "test_attr_10": "mean"}

    for _ in range(KEEPALIVE_TIME + 1):
        async_fire_time_changed(hass, dt_util.utcnow())
    hass.states.async_set(entity_id, state, attributes)
    for _ in range(KEEPALIVE_TIME + 1):
        async_fire_time_changed(hass, dt_util.utcnow())
    hass.states.async_set(entity_id, state, attributes2)

    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 2
        assert db_states[0].event_id is None


async def test_saving_state_with_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_recorder: None,
) -> None:
    """Test saving and restoring a state."""
    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    def _throw_if_state_in_session(*args, **kwargs):
        for obj in get_instance(hass).event_session:
            if isinstance(obj, States):
                raise OperationalError(
                    "insert the state", "fake params", "forced to fail"
                )

    with (
        patch("time.sleep"),
        patch.object(
            get_instance(hass).event_session,
            "flush",
            side_effect=_throw_if_state_in_session,
        ),
    ):
        hass.states.async_set(entity_id, "fail", attributes)
        await async_wait_recording_done(hass)

    assert "Error executing query" in caplog.text
    assert "Error saving events" not in caplog.text

    caplog.clear()
    hass.states.async_set(entity_id, state, attributes)
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        db_states = list(session.query(States))
        assert len(db_states) >= 1

    assert "Error executing query" not in caplog.text
    assert "Error saving events" not in caplog.text


async def test_saving_state_with_sqlalchemy_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_recorder: None,
) -> None:
    """Test saving state when there is an SQLAlchemyError."""
    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    def _throw_if_state_in_session(*args, **kwargs):
        for obj in get_instance(hass).event_session:
            if isinstance(obj, States):
                raise SQLAlchemyError(
                    "insert the state", "fake params", "forced to fail"
                )

    with (
        patch("time.sleep"),
        patch.object(
            get_instance(hass).event_session,
            "flush",
            side_effect=_throw_if_state_in_session,
        ),
    ):
        hass.states.async_set(entity_id, "fail", attributes)
        await async_wait_recording_done(hass)

    assert "SQLAlchemyError error processing task" in caplog.text

    caplog.clear()
    hass.states.async_set(entity_id, state, attributes)
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        db_states = list(session.query(States))
        assert len(db_states) >= 1

    assert "Error executing query" not in caplog.text
    assert "Error saving events" not in caplog.text
    assert "SQLAlchemyError error processing task" not in caplog.text


async def test_force_shutdown_with_queue_of_writes_that_generate_exceptions(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test forcing shutdown."""
    instance = await async_setup_recorder_instance(hass)

    entity_id = "test.recorder"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    await async_wait_recording_done(hass)

    with (
        patch.object(instance, "db_retry_wait", 0.01),
        patch.object(
            instance.event_session,
            "flush",
            side_effect=OperationalError(
                "insert the state", "fake params", "forced to fail"
            ),
        ),
    ):
        for _ in range(100):
            hass.states.async_set(entity_id, "on", attributes)
            hass.states.async_set(entity_id, "off", attributes)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
        await hass.async_block_till_done()

    assert "Error executing query" in caplog.text
    assert "Error saving events" not in caplog.text


async def test_saving_event(hass: HomeAssistant, setup_recorder: None) -> None:
    """Test saving and restoring an event."""
    event_type = "EVENT_TEST"
    event_data = {"test_attr": 5, "test_attr_10": "nice"}

    events = []

    @callback
    def event_listener(event):
        """Record events from eventbus."""
        if event.event_type == event_type:
            events.append(event)

    hass.bus.async_listen(MATCH_ALL, event_listener)

    hass.bus.async_fire(event_type, event_data)

    await async_wait_recording_done(hass)

    assert len(events) == 1
    event: Event = events[0]

    await async_recorder_block_till_done(hass)
    events: list[Event] = []

    with session_scope(hass=hass, read_only=True) as session:
        for select_event, event_data, event_types in (
            session.query(Events, EventData, EventTypes)
            .filter(Events.event_type_id.in_(select_event_type_ids((event_type,))))
            .outerjoin(EventTypes, (Events.event_type_id == EventTypes.event_type_id))
            .outerjoin(EventData, Events.data_id == EventData.data_id)
        ):
            select_event = cast(Events, select_event)
            event_data = cast(EventData, event_data)
            event_types = cast(EventTypes, event_types)

            native_event = select_event.to_native()
            native_event.data = event_data.to_native()
            native_event.event_type = event_types.event_type
            events.append(native_event)

    db_event = events[0]

    assert event.event_type == db_event.event_type
    assert event.data == db_event.data
    assert event.origin == db_event.origin

    # Recorder uses SQLite and stores datetimes as integer unix timestamps
    assert event.time_fired.replace(microsecond=0) == db_event.time_fired.replace(
        microsecond=0
    )


async def test_saving_state_with_commit_interval_zero(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving a state with a commit interval of zero."""
    await async_setup_recorder_instance(hass, {"commit_interval": 0})
    assert get_instance(hass).commit_interval == 0

    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.async_set(entity_id, state, attributes)

    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 1
        assert db_states[0].event_id is None


async def _add_entities(hass, entity_ids):
    """Add entities."""
    attributes = {"test_attr": 5, "test_attr_10": "nice"}
    for idx, entity_id in enumerate(entity_ids):
        hass.states.async_set(entity_id, f"state{idx}", attributes)
    await async_wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        states = []
        for db_state, db_state_attributes, states_meta in (
            session.query(States, StateAttributes, StatesMeta)
            .outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            )
            .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
        ):
            db_state.entity_id = states_meta.entity_id
            native_state = db_state.to_native()
            native_state.attributes = db_state_attributes.to_native()
            states.append(native_state)
        convert_pending_states_to_meta(get_instance(hass), session)
        return states


def _state_with_context(hass, entity_id):
    # We don't restore context unless we need it by joining the
    # events table on the event_id for state_changed events
    return hass.states.get(entity_id)


async def test_setup_without_migration(
    hass: HomeAssistant, setup_recorder: None
) -> None:
    """Verify the schema version without a migration."""
    assert recorder.get_instance(hass).schema_version == SCHEMA_VERSION


async def test_saving_state_include_domains(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(hass, {"include": {"domains": "test2"}})
    states = await _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder").as_dict() == states[0].as_dict()


async def test_saving_state_include_domains_globs(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(
        hass, {"include": {"domains": "test2", "entity_globs": "*.included_*"}}
    )
    states = await _add_entities(
        hass, ["test.recorder", "test2.recorder", "test3.included_entity"]
    )
    assert len(states) == 2
    state_map = {state.entity_id: state for state in states}

    assert (
        _state_with_context(hass, "test2.recorder").as_dict()
        == state_map["test2.recorder"].as_dict()
    )
    assert (
        _state_with_context(hass, "test3.included_entity").as_dict()
        == state_map["test3.included_entity"].as_dict()
    )


async def test_saving_state_incl_entities(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(
        hass, {"include": {"entities": "test2.recorder"}}
    )
    states = await _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder").as_dict() == states[0].as_dict()


async def test_saving_event_exclude_event_type(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring an event."""
    config = {
        "exclude": {
            "event_types": [
                "service_registered",
                "homeassistant_start",
                "component_loaded",
                "core_config_updated",
                "homeassistant_started",
                "test",
            ]
        }
    }
    instance = await async_setup_recorder_instance(hass, config)
    events = ["test", "test2"]
    for event_type in events:
        hass.bus.async_fire(event_type)

    await async_wait_recording_done(hass)

    def _get_events(hass: HomeAssistant, event_types: list[str]) -> list[Event]:
        with session_scope(hass=hass, read_only=True) as session:
            events = []
            for event, event_data, event_types in (
                session.query(Events, EventData, EventTypes)
                .outerjoin(
                    EventTypes, (Events.event_type_id == EventTypes.event_type_id)
                )
                .outerjoin(EventData, Events.data_id == EventData.data_id)
                .where(EventTypes.event_type.in_(event_types))
            ):
                event = cast(Events, event)
                event_data = cast(EventData, event_data)
                event_types = cast(EventTypes, event_types)

                native_event = event.to_native()
                if event_data:
                    native_event.data = event_data.to_native()
                native_event.event_type = event_types.event_type
                events.append(native_event)
            return events

    events = await instance.async_add_executor_job(_get_events, hass, ["test", "test2"])
    assert len(events) == 1
    assert events[0].event_type == "test2"


async def test_saving_state_exclude_domains(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(hass, {"exclude": {"domains": "test"}})
    states = await _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder").as_dict() == states[0].as_dict()


async def test_saving_state_exclude_domains_globs(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(
        hass, {"exclude": {"domains": "test", "entity_globs": "*.excluded_*"}}
    )
    states = await _add_entities(
        hass, ["test.recorder", "test2.recorder", "test2.excluded_entity"]
    )
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder").as_dict() == states[0].as_dict()


async def test_saving_state_exclude_entities(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(
        hass, {"exclude": {"entities": "test.recorder"}}
    )
    states = await _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder").as_dict() == states[0].as_dict()


async def test_saving_state_exclude_domain_include_entity(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(
        hass,
        {
            "include": {"entities": "test.recorder"},
            "exclude": {"domains": "test"},
        },
    )
    states = await _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 2


async def test_saving_state_exclude_domain_glob_include_entity(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(
        hass,
        {
            "include": {"entities": ["test.recorder", "test.excluded_entity"]},
            "exclude": {"domains": "test", "entity_globs": "*._excluded_*"},
        },
    )
    states = await _add_entities(
        hass, ["test.recorder", "test2.recorder", "test.excluded_entity"]
    )
    assert len(states) == 3


async def test_saving_state_include_domain_exclude_entity(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(
        hass,
        {
            "exclude": {"entities": "test.recorder"},
            "include": {"domains": "test"},
        },
    )
    states = await _add_entities(hass, ["test.recorder", "test2.recorder", "test.ok"])
    assert len(states) == 1
    assert _state_with_context(hass, "test.ok").as_dict() == states[0].as_dict()
    assert _state_with_context(hass, "test.ok").state == "state2"


async def test_saving_state_include_domain_glob_exclude_entity(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test saving and restoring a state."""
    await async_setup_recorder_instance(
        hass,
        {
            "exclude": {"entities": ["test.recorder", "test2.included_entity"]},
            "include": {"domains": "test", "entity_globs": "*._included_*"},
        },
    )
    states = await _add_entities(
        hass, ["test.recorder", "test2.recorder", "test.ok", "test2.included_entity"]
    )
    assert len(states) == 1
    assert _state_with_context(hass, "test.ok").as_dict() == states[0].as_dict()
    assert _state_with_context(hass, "test.ok").state == "state2"


async def test_saving_state_and_removing_entity(
    hass: HomeAssistant,
    setup_recorder: None,
) -> None:
    """Test saving the state of a removed entity."""
    entity_id = "lock.mine"
    hass.states.async_set(entity_id, STATE_LOCKED)
    hass.states.async_set(entity_id, STATE_UNLOCKED)
    hass.states.async_remove(entity_id)

    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        states = list(
            session.query(StatesMeta.entity_id, States.state)
            .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
            .order_by(States.last_updated_ts)
        )
        assert len(states) == 3
        assert states[0].entity_id == entity_id
        assert states[0].state == STATE_LOCKED
        assert states[1].entity_id == entity_id
        assert states[1].state == STATE_UNLOCKED
        assert states[2].entity_id == entity_id
        assert states[2].state is None


async def test_saving_state_with_oversized_attributes(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_recorder: None,
) -> None:
    """Test saving states is limited to 16KiB of JSON encoded attributes."""
    massive_dict = {"a": "b" * 16384}
    attributes = {"test_attr": 5, "test_attr_10": "nice"}
    hass.states.async_set("switch.sane", "on", attributes)
    hass.states.async_set("switch.too_big", "on", massive_dict)
    await async_wait_recording_done(hass)
    states = []

    with session_scope(hass=hass, read_only=True) as session:
        for db_state, db_state_attributes, states_meta in (
            session.query(States, StateAttributes, StatesMeta)
            .outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            )
            .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
        ):
            db_state.entity_id = states_meta.entity_id
            native_state = db_state.to_native()
            native_state.attributes = db_state_attributes.to_native()
            states.append(native_state)

    assert "switch.too_big" in caplog.text

    assert len(states) == 2
    assert _state_with_context(hass, "switch.sane").as_dict() == states[0].as_dict()
    assert states[1].state == "on"
    assert states[1].entity_id == "switch.too_big"
    assert states[1].attributes == {}


async def test_saving_event_with_oversized_data(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_recorder: None,
) -> None:
    """Test saving events is limited to 32KiB of JSON encoded data."""
    massive_dict = {"a": "b" * 32768}
    event_data = {"test_attr": 5, "test_attr_10": "nice"}
    hass.bus.async_fire("test_event", event_data)
    hass.bus.async_fire("test_event_too_big", massive_dict)
    await async_wait_recording_done(hass)
    events = {}

    with session_scope(hass=hass, read_only=True) as session:
        for _, data, event_type in (
            session.query(Events.event_id, EventData.shared_data, EventTypes.event_type)
            .outerjoin(EventData, Events.data_id == EventData.data_id)
            .outerjoin(EventTypes, Events.event_type_id == EventTypes.event_type_id)
            .where(EventTypes.event_type.in_(["test_event", "test_event_too_big"]))
        ):
            events[event_type] = data

    assert "test_event_too_big" in caplog.text

    assert len(events) == 2
    assert json_loads(events["test_event"]) == event_data
    assert json_loads(events["test_event_too_big"]) == {}


async def test_saving_event_invalid_context_ulid(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_recorder: None,
) -> None:
    """Test we handle invalid manually injected context ids."""
    event_data = {"test_attr": 5, "test_attr_10": "nice"}
    hass.bus.async_fire("test_event", event_data, context=Context(id="invalid"))
    await async_wait_recording_done(hass)
    events = {}

    with session_scope(hass=hass, read_only=True) as session:
        for _, data, event_type in (
            session.query(Events.event_id, EventData.shared_data, EventTypes.event_type)
            .outerjoin(EventData, Events.data_id == EventData.data_id)
            .outerjoin(EventTypes, Events.event_type_id == EventTypes.event_type_id)
            .where(EventTypes.event_type.in_(["test_event"]))
        ):
            events[event_type] = data

    assert "invalid" in caplog.text

    assert len(events) == 1
    assert json_loads(events["test_event"]) == event_data


async def test_recorder_setup_failure(hass: HomeAssistant) -> None:
    """Test some exceptions."""
    recorder_helper.async_initialize_recorder(hass)
    with (
        patch.object(Recorder, "_setup_connection") as setup,
        patch("homeassistant.components.recorder.core.time.sleep"),
    ):
        setup.side_effect = ImportError("driver not found")
        rec = _default_recorder(hass)
        rec.async_initialize()
        rec.start()
        rec.join()

    hass.stop()


async def test_recorder_validate_schema_failure(hass: HomeAssistant) -> None:
    """Test some exceptions."""
    recorder_helper.async_initialize_recorder(hass)
    with (
        patch(
            "homeassistant.components.recorder.migration._get_schema_version"
        ) as inspect_schema_version,
        patch("homeassistant.components.recorder.core.time.sleep"),
    ):
        inspect_schema_version.side_effect = ImportError("driver not found")
        rec = _default_recorder(hass)
        rec.async_initialize()
        rec.start()
        rec.join()

    hass.stop()


async def test_recorder_setup_failure_without_event_listener(
    hass: HomeAssistant,
) -> None:
    """Test recorder setup failure when the event listener is not setup."""
    recorder_helper.async_initialize_recorder(hass)
    with (
        patch.object(Recorder, "_setup_connection") as setup,
        patch("homeassistant.components.recorder.core.time.sleep"),
    ):
        setup.side_effect = ImportError("driver not found")
        rec = _default_recorder(hass)
        rec.start()
        rec.join()

    hass.stop()


async def test_defaults_set(hass: HomeAssistant) -> None:
    """Test the config defaults are set."""
    recorder_config = None

    async def mock_setup(hass, config):
        """Mock setup."""
        nonlocal recorder_config
        recorder_config = config["recorder"]
        return True

    with patch("homeassistant.components.recorder.async_setup", side_effect=mock_setup):
        assert await async_setup_component(hass, "history", {})

    assert recorder_config is not None
    assert recorder_config["auto_purge"]
    assert recorder_config["auto_repack"]
    assert recorder_config["purge_keep_days"] == 10


async def run_tasks_at_time(hass: HomeAssistant, test_time: datetime) -> None:
    """Advance the clock and wait for any callbacks to finish."""
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_recorder_block_till_done(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize("enable_nightly_purge", [True])
async def test_auto_purge(hass: HomeAssistant, setup_recorder: None) -> None:
    """Test periodic purge scheduling."""
    timezone = "Europe/Copenhagen"
    await hass.config.async_set_time_zone(timezone)
    tz = dt_util.get_time_zone(timezone)

    # Purging is scheduled to happen at 4:12am every day. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    await run_tasks_at_time(hass, test_time)

    with (
        patch(
            "homeassistant.components.recorder.purge.purge_old_data", return_value=True
        ) as purge_old_data,
        patch(
            "homeassistant.components.recorder.tasks.periodic_db_cleanups"
        ) as periodic_db_cleanups,
    ):
        assert len(purge_old_data.mock_calls) == 0
        assert len(periodic_db_cleanups.mock_calls) == 0

        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        await run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        assert len(periodic_db_cleanups.mock_calls) == 1

        purge_old_data.reset_mock()
        periodic_db_cleanups.reset_mock()

        # Advance one day, and the purge task should run again
        test_time = test_time + timedelta(days=1)
        await run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        assert len(periodic_db_cleanups.mock_calls) == 1

        purge_old_data.reset_mock()
        periodic_db_cleanups.reset_mock()

        # Advance less than one full day.  The alarm should not yet fire.
        test_time = test_time + timedelta(hours=23)
        await run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 0
        assert len(periodic_db_cleanups.mock_calls) == 0

        # Advance to the next day and fire the alarm again
        test_time = test_time + timedelta(hours=1)
        await run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        assert len(periodic_db_cleanups.mock_calls) == 1


@pytest.mark.parametrize("enable_nightly_purge", [True])
async def test_auto_purge_auto_repack_on_second_sunday(
    hass: HomeAssistant,
    setup_recorder: None,
) -> None:
    """Test periodic purge scheduling does a repack on the 2nd sunday."""
    timezone = "Europe/Copenhagen"
    await hass.config.async_set_time_zone(timezone)
    tz = dt_util.get_time_zone(timezone)

    # Purging is scheduled to happen at 4:12am every day. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    await run_tasks_at_time(hass, test_time)

    with (
        patch(
            "homeassistant.components.recorder.core.is_second_sunday", return_value=True
        ),
        patch(
            "homeassistant.components.recorder.purge.purge_old_data", return_value=True
        ) as purge_old_data,
        patch(
            "homeassistant.components.recorder.tasks.periodic_db_cleanups"
        ) as periodic_db_cleanups,
    ):
        assert len(purge_old_data.mock_calls) == 0
        assert len(periodic_db_cleanups.mock_calls) == 0

        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        await run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        args, _ = purge_old_data.call_args_list[0]
        assert args[2] is True  # repack
        assert len(periodic_db_cleanups.mock_calls) == 1


@pytest.mark.parametrize("enable_nightly_purge", [True])
async def test_auto_purge_auto_repack_disabled_on_second_sunday(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test periodic purge scheduling does not auto repack on the 2nd sunday if disabled."""
    timezone = "Europe/Copenhagen"
    await hass.config.async_set_time_zone(timezone)
    await async_setup_recorder_instance(hass, {CONF_AUTO_REPACK: False})
    tz = dt_util.get_time_zone(timezone)

    # Purging is scheduled to happen at 4:12am every day. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    await run_tasks_at_time(hass, test_time)

    with (
        patch(
            "homeassistant.components.recorder.core.is_second_sunday", return_value=True
        ),
        patch(
            "homeassistant.components.recorder.purge.purge_old_data", return_value=True
        ) as purge_old_data,
        patch(
            "homeassistant.components.recorder.tasks.periodic_db_cleanups"
        ) as periodic_db_cleanups,
    ):
        assert len(purge_old_data.mock_calls) == 0
        assert len(periodic_db_cleanups.mock_calls) == 0

        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        await run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        args, _ = purge_old_data.call_args_list[0]
        assert args[2] is False  # repack
        assert len(periodic_db_cleanups.mock_calls) == 1


@pytest.mark.parametrize("enable_nightly_purge", [True])
async def test_auto_purge_no_auto_repack_on_not_second_sunday(
    hass: HomeAssistant,
    setup_recorder: None,
) -> None:
    """Test periodic purge scheduling does not do a repack unless its the 2nd sunday."""
    timezone = "Europe/Copenhagen"
    await hass.config.async_set_time_zone(timezone)
    tz = dt_util.get_time_zone(timezone)

    # Purging is scheduled to happen at 4:12am every day. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    await run_tasks_at_time(hass, test_time)

    with (
        patch(
            "homeassistant.components.recorder.core.is_second_sunday",
            return_value=False,
        ),
        patch(
            "homeassistant.components.recorder.purge.purge_old_data", return_value=True
        ) as purge_old_data,
        patch(
            "homeassistant.components.recorder.tasks.periodic_db_cleanups"
        ) as periodic_db_cleanups,
    ):
        assert len(purge_old_data.mock_calls) == 0
        assert len(periodic_db_cleanups.mock_calls) == 0

        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        await run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        args, _ = purge_old_data.call_args_list[0]
        assert args[2] is False  # repack
        assert len(periodic_db_cleanups.mock_calls) == 1


@pytest.mark.parametrize("enable_nightly_purge", [True])
async def test_auto_purge_disabled(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test periodic db cleanup still run when auto purge is disabled."""
    timezone = "Europe/Copenhagen"
    await hass.config.async_set_time_zone(timezone)
    await async_setup_recorder_instance(hass, {CONF_AUTO_PURGE: False})
    tz = dt_util.get_time_zone(timezone)

    # Purging is scheduled to happen at 4:12am every day. We want
    # to verify that when auto purge is disabled periodic db cleanups
    # are still scheduled
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    await run_tasks_at_time(hass, test_time)

    with (
        patch(
            "homeassistant.components.recorder.purge.purge_old_data", return_value=True
        ) as purge_old_data,
        patch(
            "homeassistant.components.recorder.tasks.periodic_db_cleanups"
        ) as periodic_db_cleanups,
    ):
        assert len(purge_old_data.mock_calls) == 0
        assert len(periodic_db_cleanups.mock_calls) == 0

        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        await run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 0
        assert len(periodic_db_cleanups.mock_calls) == 1

        purge_old_data.reset_mock()
        periodic_db_cleanups.reset_mock()


@pytest.mark.parametrize("enable_statistics", [True])
async def test_auto_statistics(
    hass: HomeAssistant,
    setup_recorder: None,
    freezer,
) -> None:
    """Test periodic statistics scheduling."""
    timezone = "Europe/Copenhagen"
    await hass.config.async_set_time_zone(timezone)
    tz = dt_util.get_time_zone(timezone)

    stats_5min = []
    stats_hourly = []

    @callback
    def async_5min_stats_updated_listener(event: Event) -> None:
        """Handle recorder 5 min stat updated."""
        stats_5min.append(event)

    @callback
    def async_hourly_stats_updated_listener(event: Event) -> None:
        """Handle recorder 5 min stat updated."""
        stats_hourly.append(event)

    # Statistics is scheduled to happen every 5 minutes. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:51am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 51, 0, tzinfo=tz)
    freezer.move_to(test_time.isoformat())
    await run_tasks_at_time(hass, test_time)

    hass.bus.async_listen(
        EVENT_RECORDER_5MIN_STATISTICS_GENERATED, async_5min_stats_updated_listener
    )
    hass.bus.async_listen(
        EVENT_RECORDER_HOURLY_STATISTICS_GENERATED, async_hourly_stats_updated_listener
    )

    real_compile_statistics = statistics.compile_statistics
    with patch(
        "homeassistant.components.recorder.statistics.compile_statistics",
        side_effect=real_compile_statistics,
        autospec=True,
    ) as compile_statistics:
        # Advance 5 minutes, and the statistics task should run
        test_time = test_time + timedelta(minutes=5)
        freezer.move_to(test_time.isoformat())
        await run_tasks_at_time(hass, test_time)
        assert len(compile_statistics.mock_calls) == 1
        assert len(stats_5min) == 1
        assert len(stats_hourly) == 0

        compile_statistics.reset_mock()

        # Advance 5 minutes, and the statistics task should run again
        test_time = test_time + timedelta(minutes=5, seconds=1)
        freezer.move_to(test_time.isoformat())
        await run_tasks_at_time(hass, test_time)
        assert len(compile_statistics.mock_calls) == 1
        assert len(stats_5min) == 2
        assert len(stats_hourly) == 1

        compile_statistics.reset_mock()

        # Advance less than 5 minutes. The task should not run.
        test_time = test_time + timedelta(minutes=3)
        freezer.move_to(test_time.isoformat())
        await run_tasks_at_time(hass, test_time)
        assert len(compile_statistics.mock_calls) == 0
        assert len(stats_5min) == 2
        assert len(stats_hourly) == 1

        # Advance 5 minutes, and the statistics task should run again
        test_time = test_time + timedelta(minutes=5, seconds=1)
        freezer.move_to(test_time.isoformat())
        await run_tasks_at_time(hass, test_time)
        assert len(compile_statistics.mock_calls) == 1
        assert len(stats_5min) == 3
        assert len(stats_hourly) == 1


async def test_statistics_runs_initiated(
    hass: HomeAssistant, async_setup_recorder_instance: RecorderInstanceGenerator
) -> None:
    """Test statistics_runs is initiated when DB is created."""
    now = dt_util.utcnow()
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=now
    ):
        await async_setup_recorder_instance(hass)

        await async_wait_recording_done(hass)

        with session_scope(hass=hass, read_only=True) as session:
            statistics_runs = list(session.query(StatisticsRuns))
            assert len(statistics_runs) == 1
            last_run = process_timestamp(statistics_runs[0].start)
            assert process_timestamp(last_run) == now.replace(
                minute=now.minute - now.minute % 5, second=0, microsecond=0
            ) - timedelta(minutes=5)


@pytest.mark.freeze_time("2022-09-13 09:00:00+02:00")
async def test_compile_missing_statistics(
    tmp_path: Path, freezer: FrozenDateTimeFactory
) -> None:
    """Test missing statistics are compiled on startup."""
    now = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    test_dir = tmp_path.joinpath("sqlite")
    test_dir.mkdir()
    test_db_file = test_dir.joinpath("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    def get_statistic_runs(hass: HomeAssistant) -> list:
        with session_scope(hass=hass, read_only=True) as session:
            return list(session.query(StatisticsRuns))

    async with async_test_home_assistant() as hass:
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl}})
        await hass.async_start()
        await async_wait_recording_done(hass)
        await async_wait_recording_done(hass)

        instance = recorder.get_instance(hass)
        statistics_runs = await instance.async_add_executor_job(
            get_statistic_runs, hass
        )
        assert len(statistics_runs) == 1
        last_run = process_timestamp(statistics_runs[0].start)
        assert last_run == now - timedelta(minutes=5)

        await async_wait_recording_done(hass)
        await async_wait_recording_done(hass)
        await hass.async_stop()

    # Start Home Assistant one hour later
    stats_5min = []
    stats_hourly = []

    @callback
    def async_5min_stats_updated_listener(event: Event) -> None:
        """Handle recorder 5 min stat updated."""
        stats_5min.append(event)

    def async_hourly_stats_updated_listener(event: Event) -> None:
        """Handle recorder 5 min stat updated."""
        stats_hourly.append(event)

    freezer.tick(timedelta(hours=1))
    async with async_test_home_assistant() as hass:
        hass.bus.async_listen(
            EVENT_RECORDER_5MIN_STATISTICS_GENERATED, async_5min_stats_updated_listener
        )
        hass.bus.async_listen(
            EVENT_RECORDER_HOURLY_STATISTICS_GENERATED,
            async_hourly_stats_updated_listener,
        )

        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl}})
        await hass.async_start()
        await async_wait_recording_done(hass)
        await async_wait_recording_done(hass)

        instance = recorder.get_instance(hass)
        statistics_runs = await instance.async_add_executor_job(
            get_statistic_runs, hass
        )
        assert len(statistics_runs) == 13  # 12 5-minute runs
        last_run = process_timestamp(statistics_runs[1].start)
        assert last_run == now

        assert len(stats_5min) == 1
        assert len(stats_hourly) == 1

        await async_wait_recording_done(hass)
        await async_wait_recording_done(hass)
        await hass.async_stop()


async def test_saving_sets_old_state(hass: HomeAssistant, setup_recorder: None) -> None:
    """Test saving sets old state."""
    hass.states.async_set("test.one", "s1", {})
    hass.states.async_set("test.two", "s2", {})
    hass.states.async_set("test.one", "s3", {})
    hass.states.async_set("test.two", "s4", {})
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        states = list(
            session.query(
                StatesMeta.entity_id, States.state_id, States.old_state_id, States.state
            ).outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
        )
        assert len(states) == 4
        states_by_state = {state.state: state for state in states}

        assert states_by_state["s1"].entity_id == "test.one"
        assert states_by_state["s2"].entity_id == "test.two"
        assert states_by_state["s3"].entity_id == "test.one"
        assert states_by_state["s4"].entity_id == "test.two"

        assert states_by_state["s1"].old_state_id is None
        assert states_by_state["s2"].old_state_id is None
        assert states_by_state["s3"].old_state_id == states_by_state["s1"].state_id
        assert states_by_state["s4"].old_state_id == states_by_state["s2"].state_id


async def test_saving_state_with_serializable_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, setup_recorder: None
) -> None:
    """Test saving data that cannot be serialized does not crash."""
    hass.bus.async_fire("bad_event", {"fail": CannotSerializeMe()})
    hass.states.async_set("test.one", "s1", {"fail": CannotSerializeMe()})
    hass.states.async_set("test.two", "s2", {})
    hass.states.async_set("test.two", "s3", {})
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        states = list(
            session.query(
                StatesMeta.entity_id, States.state_id, States.old_state_id, States.state
            ).outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
        )
        assert len(states) == 2
        states_by_state = {state.state: state for state in states}
        assert states_by_state["s2"].entity_id == "test.two"
        assert states_by_state["s3"].entity_id == "test.two"
        assert states_by_state["s2"].old_state_id is None
        assert states_by_state["s3"].old_state_id == states_by_state["s2"].state_id

    assert "State is not JSON serializable" in caplog.text


async def test_has_services(hass: HomeAssistant, setup_recorder: None) -> None:
    """Test the services exist."""
    assert hass.services.has_service(DOMAIN, SERVICE_DISABLE)
    assert hass.services.has_service(DOMAIN, SERVICE_ENABLE)
    assert hass.services.has_service(DOMAIN, SERVICE_PURGE)
    assert hass.services.has_service(DOMAIN, SERVICE_PURGE_ENTITIES)


async def test_service_disable_events_not_recording(
    hass: HomeAssistant,
    setup_recorder: None,
) -> None:
    """Test that events are not recorded when recorder is disabled using service."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DISABLE,
        {},
        blocking=True,
    )

    event_type = "EVENT_TEST"

    events = []

    @callback
    def event_listener(event):
        """Record events from eventbus."""
        if event.event_type == event_type:
            events.append(event)

    hass.bus.async_listen(MATCH_ALL, event_listener)

    event_data1 = {"test_attr": 5, "test_attr_10": "nice"}
    hass.bus.async_fire(event_type, event_data1)
    await async_wait_recording_done(hass)

    assert len(events) == 1
    event = events[0]

    with session_scope(hass=hass, read_only=True) as session:
        db_events = list(
            session.query(Events)
            .filter(Events.event_type_id.in_(select_event_type_ids((event_type,))))
            .outerjoin(EventTypes, (Events.event_type_id == EventTypes.event_type_id))
        )
        assert len(db_events) == 0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ENABLE,
        {},
        blocking=True,
    )

    event_data2 = {"attr_one": 5, "attr_two": "nice"}
    hass.bus.async_fire(event_type, event_data2)
    await async_wait_recording_done(hass)

    assert len(events) == 2
    assert events[0] != events[1]
    assert events[0].data != events[1].data

    db_events = []
    with session_scope(hass=hass, read_only=True) as session:
        for select_event, event_data, event_types in (
            session.query(Events, EventData, EventTypes)
            .filter(Events.event_type_id.in_(select_event_type_ids((event_type,))))
            .outerjoin(EventTypes, (Events.event_type_id == EventTypes.event_type_id))
            .outerjoin(EventData, Events.data_id == EventData.data_id)
        ):
            select_event = cast(Events, select_event)
            event_data = cast(EventData, event_data)
            event_types = cast(EventTypes, event_types)

            native_event = select_event.to_native()
            native_event.data = event_data.to_native()
            native_event.event_type = event_types.event_type
            db_events.append(native_event)

    assert len(db_events) == 1
    db_event = db_events[0]
    event = events[1]

    assert event.event_type == db_event.event_type
    assert event.data == db_event.data
    assert event.origin == db_event.origin
    assert event.time_fired.replace(microsecond=0) == db_event.time_fired.replace(
        microsecond=0
    )


async def test_service_disable_states_not_recording(
    hass: HomeAssistant,
    setup_recorder: None,
) -> None:
    """Test that state changes are not recorded when recorder is disabled using service."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DISABLE,
        {},
        blocking=True,
    )

    hass.states.async_set("test.one", "on", {})
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        assert len(list(session.query(States))) == 0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ENABLE,
        {},
        blocking=True,
    )

    hass.states.async_set("test.two", "off", {})
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 1
        assert db_states[0].event_id is None
        db_states[0].entity_id = "test.two"
        assert (
            db_states[0].to_native().as_dict()
            == _state_with_context(hass, "test.two").as_dict()
        )


async def test_service_disable_run_information_recorded(tmp_path: Path) -> None:
    """Test that runs are still recorded when recorder is disabled."""
    test_dir = tmp_path.joinpath("sqlite")
    test_dir.mkdir()
    test_db_file = test_dir.joinpath("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    def get_recorder_runs(hass: HomeAssistant) -> list:
        with session_scope(hass=hass, read_only=True) as session:
            return list(session.query(RecorderRuns))

    async with async_test_home_assistant() as hass:
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl}})
        await hass.async_start()
        await async_wait_recording_done(hass)

        instance = recorder.get_instance(hass)
        db_run_info = await instance.async_add_executor_job(get_recorder_runs, hass)
        assert len(db_run_info) == 1
        assert db_run_info[0].start is not None
        assert db_run_info[0].end is None

        await hass.services.async_call(
            DOMAIN,
            SERVICE_DISABLE,
            {},
            blocking=True,
        )

        await async_wait_recording_done(hass)
        await hass.async_stop()

    async with async_test_home_assistant() as hass:
        recorder_helper.async_initialize_recorder(hass)
        await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl}})
        await hass.async_start()
        await async_wait_recording_done(hass)

        instance = recorder.get_instance(hass)
        db_run_info = await instance.async_add_executor_job(get_recorder_runs, hass)
        assert len(db_run_info) == 2
        assert db_run_info[0].start is not None
        assert db_run_info[0].end is not None
        assert db_run_info[1].start is not None
        assert db_run_info[1].end is None

        await hass.async_stop()


class CannotSerializeMe:
    """A class that the JSONEncoder cannot serialize."""


async def test_database_corruption_while_running(
    hass: HomeAssistant, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can recover from sqlite3 db corruption."""

    def _create_tmpdir_for_test_db() -> Path:
        test_dir = tmp_path.joinpath("sqlite")
        test_dir.mkdir()
        return test_dir.joinpath("test.db")

    test_db_file = await hass.async_add_executor_job(_create_tmpdir_for_test_db)
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    recorder_helper.async_initialize_recorder(hass)
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl, CONF_COMMIT_INTERVAL: 0}}
    )
    await hass.async_block_till_done()
    caplog.clear()

    instance = get_instance(hass)
    original_start_time = instance.recorder_runs_manager.recording_start

    hass.states.async_set("test.lost", "on", {})

    sqlite3_exception = DatabaseError("statement", {}, [])
    sqlite3_exception.__cause__ = sqlite3.DatabaseError()

    await async_wait_recording_done(hass)
    with patch.object(
        get_instance(hass).event_session,
        "close",
        side_effect=OperationalError("statement", {}, []),
    ):
        await async_wait_recording_done(hass)
        await hass.async_add_executor_job(corrupt_db_file, test_db_file)
        await async_wait_recording_done(hass)

        with patch.object(
            get_instance(hass).event_session,
            "commit",
            side_effect=[sqlite3_exception, None],
        ):
            # This state will not be recorded because
            # the database corruption will be discovered
            # and we will have to rollback to recover
            hass.states.async_set("test.one", "off", {})
            await async_wait_recording_done(hass)

    assert "Unrecoverable sqlite3 database corruption detected" in caplog.text
    assert "The system will rename the corrupt database file" in caplog.text
    assert "Connected to recorder database" in caplog.text

    # This state should go into the new database
    hass.states.async_set("test.two", "on", {})
    await async_wait_recording_done(hass)

    def _get_last_state():
        with session_scope(hass=hass, read_only=True) as session:
            db_states = list(session.query(States))
            assert len(db_states) == 1
            db_states[0].entity_id = "test.two"
            assert db_states[0].event_id is None
            return db_states[0].to_native()

    state = await instance.async_add_executor_job(_get_last_state)
    assert state.entity_id == "test.two"
    assert state.state == "on"

    new_start_time = instance.recorder_runs_manager.recording_start
    assert original_start_time < new_start_time

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    hass.stop()


async def test_entity_id_filter(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test that entity ID filtering filters string and list."""
    await async_setup_recorder_instance(
        hass,
        {
            "include": {"domains": "hello"},
            "exclude": {"domains": "hidden_domain"},
        },
    )
    event_types = ("hello",)

    for idx, data in enumerate(
        (
            {},
            {"entity_id": "hello.world"},
            {"entity_id": ["hello.world"]},
            {"entity_id": ["hello.world", "hidden_domain.person"]},
            {"entity_id": {"unexpected": "data"}},
        )
    ):
        hass.bus.async_fire("hello", data)
        await async_wait_recording_done(hass)

        with session_scope(hass=hass, read_only=True) as session:
            db_events = list(
                session.query(Events).filter(
                    Events.event_type_id.in_(select_event_type_ids(event_types))
                )
            )
            assert len(db_events) == idx + 1, data

    for data in (
        {"entity_id": "hidden_domain.person"},
        {"entity_id": ["hidden_domain.person"]},
    ):
        hass.bus.async_fire("hello", data)
        await async_wait_recording_done(hass)

        with session_scope(hass=hass, read_only=True) as session:
            db_events = list(
                session.query(Events).filter(
                    Events.event_type_id.in_(select_event_type_ids(event_types))
                )
            )
            # Keep referring idx + 1, as no new events are being added
            assert len(db_events) == idx + 1, data


async def test_database_lock_and_unlock(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    recorder_db_url: str,
    tmp_path: Path,
) -> None:
    """Test writing events during lock getting written after unlocking."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        # Database locking is only used for SQLite
        return

    if recorder_db_url == "sqlite://":
        # Use file DB, in memory DB cannot do write locks.
        recorder_db_url = "sqlite:///" + str(tmp_path / "pytest.db")
    config = {
        recorder.CONF_COMMIT_INTERVAL: 0,
        recorder.CONF_DB_URL: recorder_db_url,
    }
    await async_setup_recorder_instance(hass, config)
    await hass.async_block_till_done()
    event_type = "EVENT_TEST"
    event_types = (event_type,)

    def _get_db_events():
        with session_scope(hass=hass, read_only=True) as session:
            return list(
                session.query(Events).filter(
                    Events.event_type_id.in_(select_event_type_ids(event_types))
                )
            )

    instance = get_instance(hass)

    assert await instance.lock_database()

    assert not await instance.lock_database()

    event_data = {"test_attr": 5, "test_attr_10": "nice"}
    hass.bus.async_fire(event_type, event_data)
    task = asyncio.create_task(async_wait_recording_done(hass))

    # Recording can't be finished while lock is held
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(asyncio.shield(task), timeout=0.25)
        db_events = await hass.async_add_executor_job(_get_db_events)
        assert len(db_events) == 0

    assert instance.unlock_database()

    await task
    db_events = await instance.async_add_executor_job(_get_db_events)
    assert len(db_events) == 1


async def test_database_lock_and_overflow(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    recorder_db_url: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test writing events during lock leading to overflow the queue causes the database to unlock."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        # Database locking is only used for SQLite
        return pytest.skip("Database locking is only used for SQLite")

    # Use file DB, in memory DB cannot do write locks.
    if recorder_db_url == "sqlite://":
        # Use file DB, in memory DB cannot do write locks.
        recorder_db_url = "sqlite:///" + str(tmp_path / "pytest.db")
    config = {
        recorder.CONF_COMMIT_INTERVAL: 0,
        recorder.CONF_DB_URL: recorder_db_url,
    }

    def _get_db_events():
        with session_scope(hass=hass, read_only=True) as session:
            return list(
                session.query(Events).filter(
                    Events.event_type_id.in_(select_event_type_ids(event_types))
                )
            )

    with (
        patch.object(recorder.core, "MAX_QUEUE_BACKLOG_MIN_VALUE", 1),
        patch.object(recorder.core, "DB_LOCK_QUEUE_CHECK_TIMEOUT", 0.01),
        patch.object(recorder.core, "QUEUE_PERCENTAGE_ALLOWED_AVAILABLE_MEMORY", 0),
    ):
        await async_setup_recorder_instance(hass, config)
        await hass.async_block_till_done()
        event_type = "EVENT_TEST"
        event_types = (event_type,)

        instance = get_instance(hass)

        await instance.lock_database()

        event_data = {"test_attr": 5, "test_attr_10": "nice"}
        hass.bus.async_fire(event_type, event_data)

        # Check that this causes the queue to overflow and write succeeds
        # even before unlocking.
        await async_wait_recording_done(hass)

        db_events = await instance.async_add_executor_job(_get_db_events)
        assert len(db_events) == 1

        assert "Database queue backlog reached more than" in caplog.text
        assert not instance.unlock_database()

    issue = issue_registry.async_get_issue(DOMAIN, "backup_failed_out_of_resources")
    assert issue is not None
    assert "start_time" in issue.translation_placeholders
    start_time = issue.translation_placeholders["start_time"]
    assert start_time is not None
    # Should be in H:M:S format
    assert start_time.count(":") == 2


async def test_database_lock_and_overflow_checks_available_memory(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    recorder_db_url: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test writing events during lock leading to overflow the queue causes the database to unlock."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        return pytest.skip("Database locking is only used for SQLite")

    # Use file DB, in memory DB cannot do write locks.
    if recorder_db_url == "sqlite://":
        # Use file DB, in memory DB cannot do write locks.
        recorder_db_url = "sqlite:///" + str(tmp_path / "pytest.db")
    config = {
        recorder.CONF_COMMIT_INTERVAL: 0,
        recorder.CONF_DB_URL: recorder_db_url,
    }

    def _get_db_events():
        with session_scope(hass=hass, read_only=True) as session:
            return list(
                session.query(Events).filter(
                    Events.event_type_id.in_(select_event_type_ids(event_types))
                )
            )

    await async_setup_recorder_instance(hass, config)
    await hass.async_block_till_done()
    event_type = "EVENT_TEST"
    event_types = (event_type,)
    await async_wait_recording_done(hass)

    with (
        patch.object(recorder.core, "MAX_QUEUE_BACKLOG_MIN_VALUE", 1),
        patch.object(recorder.core, "QUEUE_PERCENTAGE_ALLOWED_AVAILABLE_MEMORY", 1),
        patch.object(recorder.core, "DB_LOCK_QUEUE_CHECK_TIMEOUT", 0.01),
        patch.object(
            recorder.core.Recorder,
            "_available_memory",
            return_value=recorder.core.ESTIMATED_QUEUE_ITEM_SIZE * 4,
        ),
    ):
        instance = get_instance(hass)

        await instance.lock_database()

        # Record up to the extended limit (which takes into account the available memory)
        for _ in range(2):
            event_data = {"test_attr": 5, "test_attr_10": "nice"}
            hass.bus.async_fire(event_type, event_data)

        def _wait_database_unlocked():
            return instance._database_lock_task.database_unlock.wait(0.2)

        databack_unlocked = await hass.async_add_executor_job(_wait_database_unlocked)
        assert not databack_unlocked

        db_events = await instance.async_add_executor_job(_get_db_events)
        assert len(db_events) == 0

        assert "Database queue backlog reached more than" not in caplog.text

        # Record beyond the extended limit (which takes into account the available memory)
        for _ in range(20):
            event_data = {"test_attr": 5, "test_attr_10": "nice"}
            hass.bus.async_fire(event_type, event_data)

        # Check that this causes the queue to overflow and write succeeds
        # even before unlocking.
        await async_wait_recording_done(hass)

        assert not instance.unlock_database()

        assert "Database queue backlog reached more than" in caplog.text

        db_events = await instance.async_add_executor_job(_get_db_events)
        assert len(db_events) >= 2

    issue = issue_registry.async_get_issue(DOMAIN, "backup_failed_out_of_resources")
    assert issue is not None
    assert "start_time" in issue.translation_placeholders
    start_time = issue.translation_placeholders["start_time"]
    assert start_time is not None
    # Should be in H:M:S format
    assert start_time.count(":") == 2


async def test_database_lock_timeout(
    hass: HomeAssistant, setup_recorder: None, recorder_db_url: str
) -> None:
    """Test locking database timeout when recorder stopped."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        # This test is specific for SQLite: Locking is not implemented for other engines
        return

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)

    instance = get_instance(hass)

    class BlockQueue(recorder.tasks.RecorderTask):
        event: threading.Event = threading.Event()

        def run(self, instance: Recorder) -> None:
            self.event.wait()

    block_task = BlockQueue()
    instance.queue_task(block_task)
    with patch.object(recorder.core, "DB_LOCK_TIMEOUT", 0.1):
        try:
            with pytest.raises(TimeoutError):
                await instance.lock_database()
        finally:
            instance.unlock_database()
            block_task.event.set()


async def test_database_lock_without_instance(
    hass: HomeAssistant, setup_recorder: None
) -> None:
    """Test database lock doesn't fail if instance is not initialized."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)

    instance = get_instance(hass)
    with patch.object(instance, "engine"):
        try:
            assert await instance.lock_database()
        finally:
            assert instance.unlock_database()


async def test_in_memory_database(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test connecting to an in-memory recorder is not allowed."""
    assert not await async_setup_component(
        hass, recorder.DOMAIN, {recorder.DOMAIN: {recorder.CONF_DB_URL: "sqlite://"}}
    )
    assert "In-memory SQLite database is not supported" in caplog.text


async def test_database_connection_keep_alive(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we keep alive socket based dialects."""
    with patch("homeassistant.components.recorder.Recorder.dialect_name"):
        instance = await async_setup_recorder_instance(hass)
        # We have to mock this since we don't have a mock
        # MySQL server available in tests.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await instance.async_recorder_ready.wait()

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=recorder.core.KEEPALIVE_TIME)
    )
    await async_wait_recording_done(hass)
    assert "Sending keepalive" in caplog.text


async def test_database_connection_keep_alive_disabled_on_sqlite(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    caplog: pytest.LogCaptureFixture,
    recorder_db_url: str,
) -> None:
    """Test we do not do keep alive for sqlite."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        # This test is specific for SQLite, keepalive runs on other engines
        return

    instance = await async_setup_recorder_instance(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await instance.async_recorder_ready.wait()

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=recorder.core.KEEPALIVE_TIME)
    )
    await async_wait_recording_done(hass)
    assert "Sending keepalive" not in caplog.text


async def test_deduplication_event_data_inside_commit_interval(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, setup_recorder: None
) -> None:
    """Test deduplication of event data inside the commit interval."""
    for _ in range(10):
        hass.bus.async_fire("this_event", {"de": "dupe"})
    for _ in range(10):
        hass.bus.async_fire("this_event", {"de": "dupe"})
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        event_types = ("this_event",)
        events = list(
            session.query(Events)
            .filter(Events.event_type_id.in_(select_event_type_ids(event_types)))
            .outerjoin(EventTypes, (Events.event_type_id == EventTypes.event_type_id))
            .outerjoin(EventData, (Events.data_id == EventData.data_id))
        )
        assert len(events) == 20
        first_data_id = events[0].data_id
        assert all(event.data_id == first_data_id for event in events)


async def test_deduplication_state_attributes_inside_commit_interval(
    small_cache_size: None,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_recorder: None,
) -> None:
    """Test deduplication of state attributes inside the commit interval."""
    entity_id = "test.recorder"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.async_set(entity_id, "on", attributes)
    hass.states.async_set(entity_id, "off", attributes)

    # Now exhaust the cache to ensure we go back to the db
    for attr_id in range(5):
        hass.states.async_set(entity_id, "on", {"test_attr": attr_id})
        hass.states.async_set(entity_id, "off", {"test_attr": attr_id})
    for _ in range(5):
        hass.states.async_set(entity_id, "on", attributes)
        hass.states.async_set(entity_id, "off", attributes)
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        states = list(
            session.query(States).outerjoin(
                StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
            )
        )
        assert len(states) == 22
        first_attributes_id = states[0].attributes_id
        last_attributes_id = states[-1].attributes_id
        assert first_attributes_id == last_attributes_id


async def test_async_block_till_done(
    hass: HomeAssistant, async_setup_recorder_instance: RecorderInstanceGenerator
) -> None:
    """Test we can block until recordering is done."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)

    entity_id = "test.recorder"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.async_set(entity_id, "on", attributes)
    hass.states.async_set(entity_id, "off", attributes)

    def _fetch_states():
        with session_scope(hass=hass, read_only=True) as session:
            return list(session.query(States))

    await async_block_recorder(hass, 0.1)
    await instance.async_block_till_done()
    states = await instance.async_add_executor_job(_fetch_states)
    assert len(states) == 2
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("db_url", "echo"),
    [
        ("sqlite://blabla", None),
        ("mariadb://blabla", False),
        ("mysql://blabla", False),
        ("mariadb+pymysql://blabla", False),
        ("mysql+pymysql://blabla", False),
        ("postgresql://blabla", False),
    ],
)
async def test_disable_echo(
    hass: HomeAssistant, db_url, echo, caplog: pytest.LogCaptureFixture
) -> None:
    """Test echo is disabled for non sqlite databases."""
    recorder_helper.async_initialize_recorder(hass)

    class MockEvent:
        def listen(self, _, _2, callback):
            callback(None, None)

    mock_event = MockEvent()
    with (
        patch(
            "homeassistant.components.recorder.core.create_engine"
        ) as create_engine_mock,
        patch("homeassistant.components.recorder.core.sqlalchemy_event", mock_event),
    ):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: db_url}})
        create_engine_mock.assert_called_once()
        assert create_engine_mock.mock_calls[0][2].get("echo") == echo


@pytest.mark.parametrize(
    ("config_url", "expected_connect_args"),
    [
        (
            "mariadb://user:password@SERVER_IP/DB_NAME",
            {"charset": "utf8mb4"},
        ),
        (
            "mariadb+pymysql://user:password@SERVER_IP/DB_NAME",
            {"charset": "utf8mb4"},
        ),
        (
            "mysql://user:password@SERVER_IP/DB_NAME",
            {"charset": "utf8mb4"},
        ),
        (
            "mysql+pymysql://user:password@SERVER_IP/DB_NAME",
            {"charset": "utf8mb4"},
        ),
        (
            "mysql://user:password@SERVER_IP/DB_NAME?charset=utf8mb4",
            {"charset": "utf8mb4"},
        ),
        (
            "mysql://user:password@SERVER_IP/DB_NAME?blah=bleh&charset=other",
            {"charset": "utf8mb4"},
        ),
        (
            "postgresql://blabla",
            {},
        ),
        (
            "sqlite://blabla",
            {},
        ),
    ],
)
async def test_mysql_missing_utf8mb4(
    hass: HomeAssistant, config_url, expected_connect_args
) -> None:
    """Test recorder fails to setup if charset=utf8mb4 is missing from db_url."""
    recorder_helper.async_initialize_recorder(hass)

    class MockEvent:
        def listen(self, _, _2, callback):
            callback(None, None)

    mock_event = MockEvent()
    with (
        patch(
            "homeassistant.components.recorder.core.create_engine"
        ) as create_engine_mock,
        patch("homeassistant.components.recorder.core.sqlalchemy_event", mock_event),
    ):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: config_url}})
        create_engine_mock.assert_called_once()

        connect_args = create_engine_mock.mock_calls[0][2].get("connect_args", {})
        for key, value in expected_connect_args.items():
            assert connect_args[key] == value


@pytest.mark.parametrize(
    "config_url",
    [
        "mysql://user:password@SERVER_IP/DB_NAME",
        "mysql://user:password@SERVER_IP/DB_NAME?charset=utf8mb4",
        "mysql://user:password@SERVER_IP/DB_NAME?blah=bleh&charset=other",
    ],
)
async def test_connect_args_priority(hass: HomeAssistant, config_url) -> None:
    """Test connect_args has priority over URL query."""
    connect_params = []
    recorder_helper.async_initialize_recorder(hass)

    class MockDialect:
        """Non functioning dialect, good enough that SQLAlchemy tries connecting."""

        __bases__ = []
        _has_events = False

        def __init__(*args, **kwargs): ...

        @property
        def is_async(self):
            return False

        def connect(self, *args, **params):
            nonlocal connect_params
            connect_params.append(params)
            return True

        def create_connect_args(self, url):
            return ([], {"charset": "invalid"})

        @property
        def name(self) -> str:
            return "mysql"

        @classmethod
        def import_dbapi(cls): ...

        def engine_created(*args): ...

        def get_dialect_pool_class(self, *args):
            return QueuePool

        def initialize(*args): ...

        def on_connect_url(self, url):
            return False

        def _builtin_onconnect(self): ...

    class MockEntrypoint:
        def engine_created(*_): ...

        def get_dialect_cls(*_):
            return MockDialect

    with (
        patch("sqlalchemy.engine.url.URL._get_entrypoint", MockEntrypoint),
        patch("sqlalchemy.engine.create.util.get_cls_kwargs", return_value=["echo"]),
    ):
        await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_DB_URL: config_url,
                    CONF_DB_MAX_RETRIES: 1,
                    CONF_DB_RETRY_WAIT: 0,
                }
            },
        )
    assert connect_params[0]["charset"] == "utf8mb4"


async def test_excluding_attributes_by_integration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_recorder: None,
) -> None:
    """Test that an entity can exclude attributes from being recorded."""
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "excluded_component": 10, "excluded_integration": 20}
    mock_platform(
        hass,
        "fake_integration.recorder",
        Mock(exclude_attributes=lambda hass: {"excluded"}),
    )
    hass.config.components.add("fake_integration")
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "fake_integration"})
    await hass.async_block_till_done()

    class EntityWithExcludedAttributes(MockEntity):
        _entity_component_unrecorded_attributes = frozenset({"excluded_component"})
        _unrecorded_attributes = frozenset({"excluded_integration"})

    entity_id = "test.fake_integration_recorder"
    entity_platform = MockEntityPlatform(hass, platform_name="fake_integration")
    entity = EntityWithExcludedAttributes(
        entity_id=entity_id,
        extra_state_attributes=attributes,
    )
    await entity_platform.async_add_entities([entity])
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        db_states = []
        for db_state, db_state_attributes, states_meta in (
            session.query(States, StateAttributes, StatesMeta)
            .outerjoin(
                StateAttributes, States.attributes_id == StateAttributes.attributes_id
            )
            .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
        ):
            db_state.entity_id = states_meta.entity_id
            db_states.append(db_state)
            state = db_state.to_native()
            state.attributes = db_state_attributes.to_native()
        assert len(db_states) == 1
        assert db_states[0].event_id is None

    expected = _state_with_context(hass, entity_id)
    expected.attributes = {"test_attr": 5}
    assert state.as_dict() == expected.as_dict()


async def test_lru_increases_with_many_entities(
    small_cache_size: None, hass: HomeAssistant, setup_recorder: None
) -> None:
    """Test that the recorder's internal LRU cache increases with many entities."""
    mock_entity_count = 16
    for idx in range(mock_entity_count):
        hass.states.async_set(f"test.entity{idx}", "on")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await async_wait_recording_done(hass)

    instance = get_instance(hass)
    assert instance.state_attributes_manager._id_map.get_size() == mock_entity_count * 2
    assert instance.states_meta_manager._id_map.get_size() == mock_entity_count * 2


async def test_clean_shutdown_when_recorder_thread_raises_during_initialize_database(
    hass: HomeAssistant,
) -> None:
    """Test we still shutdown cleanly when the recorder thread raises during initialize_database."""
    with (
        patch.object(migration, "initialize_database", side_effect=Exception),
        patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True),
    ):
        if recorder.DOMAIN not in hass.data:
            recorder_helper.async_initialize_recorder(hass)
        assert not await async_setup_component(
            hass,
            recorder.DOMAIN,
            {
                recorder.DOMAIN: {
                    CONF_DB_URL: "sqlite://",
                    CONF_DB_RETRY_WAIT: 0,
                    CONF_DB_MAX_RETRIES: 1,
                }
            },
        )
        await hass.async_block_till_done()

    instance = recorder.get_instance(hass)
    await hass.async_stop()
    assert instance.engine is None


async def test_clean_shutdown_when_recorder_thread_raises_during_validate_db_schema(
    hass: HomeAssistant,
) -> None:
    """Test we still shutdown cleanly when the recorder thread raises during validate_db_schema."""
    with (
        patch.object(migration, "validate_db_schema", side_effect=Exception),
        patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True),
    ):
        if recorder.DOMAIN not in hass.data:
            recorder_helper.async_initialize_recorder(hass)
        assert not await async_setup_component(
            hass,
            recorder.DOMAIN,
            {
                recorder.DOMAIN: {
                    CONF_DB_URL: "sqlite://",
                    CONF_DB_RETRY_WAIT: 0,
                    CONF_DB_MAX_RETRIES: 1,
                }
            },
        )
        await hass.async_block_till_done()

    instance = recorder.get_instance(hass)
    await hass.async_stop()
    assert instance.engine is None


async def test_clean_shutdown_when_schema_migration_fails(hass: HomeAssistant) -> None:
    """Test we still shutdown cleanly when schema migration fails."""
    with (
        patch.object(
            migration,
            "validate_db_schema",
            return_value=MagicMock(valid=False, current_version=1),
        ),
        patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True),
        patch.object(
            migration,
            "migrate_schema",
            side_effect=Exception,
        ),
    ):
        if recorder.DOMAIN not in hass.data:
            recorder_helper.async_initialize_recorder(hass)
        assert await async_setup_component(
            hass,
            recorder.DOMAIN,
            {
                recorder.DOMAIN: {
                    CONF_DB_URL: "sqlite://",
                    CONF_DB_RETRY_WAIT: 0,
                    CONF_DB_MAX_RETRIES: 1,
                }
            },
        )
        await hass.async_block_till_done()

    instance = recorder.get_instance(hass)
    await hass.async_stop()
    assert instance.engine is None


async def test_events_are_recorded_until_final_write(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Test that events are recorded until the final write."""
    instance = await async_setup_recorder_instance(hass, {})
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    hass.bus.async_fire("fake_event")
    await async_wait_recording_done(hass)

    def get_events() -> list[Event]:
        events: list[Event] = []
        with session_scope(hass=hass, read_only=True) as session:
            for select_event, event_types in (
                session.query(Events, EventTypes)
                .filter(
                    Events.event_type_id.in_(
                        select_event_type_ids(("fake_event", "after_final_write"))
                    )
                )
                .outerjoin(
                    EventTypes, (Events.event_type_id == EventTypes.event_type_id)
                )
            ):
                select_event = cast(Events, select_event)
                event_types = cast(EventTypes, event_types)

                native_event = select_event.to_native()
                native_event.event_type = event_types.event_type
                events.append(native_event)

        return events

    events = await instance.async_add_executor_job(get_events)
    assert len(events) == 1
    db_event = events[0]
    assert db_event.event_type == "fake_event"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()

    assert not instance.engine


async def test_commit_before_commits_pending_writes(
    hass: HomeAssistant,
    async_setup_recorder_instance: RecorderInstanceGenerator,
    recorder_db_url: str,
    tmp_path: Path,
) -> None:
    """Test commit_before with a non-zero commit interval.

    All of our test run with a commit interval of 0 by
    default, so we need to test this with a non-zero commit
    """
    config = {
        recorder.CONF_DB_URL: recorder_db_url,
        recorder.CONF_COMMIT_INTERVAL: 60,
    }

    recorder_helper.async_initialize_recorder(hass)
    hass.async_create_task(async_setup_recorder_instance(hass, config))
    await recorder_helper.async_wait_recorder(hass)
    instance = get_instance(hass)
    assert instance.commit_interval == 60
    verify_states_in_queue_future = hass.loop.create_future()
    verify_session_commit_future = hass.loop.create_future()

    class VerifyCommitBeforeTask(recorder.tasks.RecorderTask):
        """Task to verify that commit before ran.

        If commit_before is true, we should have no pending writes.
        """

        commit_before = True

        def run(self, instance: Recorder) -> None:
            if not instance._event_session_has_pending_writes:
                hass.loop.call_soon_threadsafe(
                    verify_session_commit_future.set_result, None
                )
                return
            hass.loop.call_soon_threadsafe(
                verify_session_commit_future.set_exception,
                RuntimeError("Session still has pending write"),
            )

    class VerifyStatesInQueueTask(recorder.tasks.RecorderTask):
        """Task to verify that states are in the queue."""

        commit_before = False

        def run(self, instance: Recorder) -> None:
            if instance._event_session_has_pending_writes:
                hass.loop.call_soon_threadsafe(
                    verify_states_in_queue_future.set_result, None
                )
                return
            hass.loop.call_soon_threadsafe(
                verify_states_in_queue_future.set_exception,
                RuntimeError("Session has no pending write"),
            )

    # First insert an event
    instance.queue_task(Event("fake_event"))
    # Next verify that the event session has pending writes
    instance.queue_task(VerifyStatesInQueueTask())
    # Finally, verify that the session was committed
    instance.queue_task(VerifyCommitBeforeTask())

    await verify_states_in_queue_future
    await verify_session_commit_future


async def test_all_tables_use_default_table_args(hass: HomeAssistant) -> None:
    """Test that all tables use the default table args."""
    for table in db_schema.Base.metadata.tables.values():
        assert table.kwargs.items() >= db_schema._DEFAULT_TABLE_ARGS.items()
