"""Tests for recorder session recovery after a mid-session database outage."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
import sqlite3
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from sqlalchemy.exc import (
    IntegrityError,
    InterfaceError,
    InternalError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.orm.session import Session

from homeassistant.components.recorder import get_instance, history
from homeassistant.components.recorder.core import Recorder
from homeassistant.components.recorder.db_schema import States
from homeassistant.components.recorder.models import UnsupportedDialect
from homeassistant.components.recorder.tasks import RecorderTask
from homeassistant.components.recorder.util import dburl_to_path, session_scope
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .common import async_wait_recording_done

from tests.typing import RecorderInstanceContextManager


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


def _raise_if_state_in_session(
    event_session: Session, exception: Exception
) -> Callable[..., None]:
    """Return a flush side effect that fails once a States row is pending."""

    def _throw_if_state_in_session(*args: object, **kwargs: object) -> None:
        for obj in event_session:
            if isinstance(obj, States):
                raise exception

    return _throw_if_state_in_session


@pytest.mark.usefixtures("recorder_mock")
async def test_oldest_ts_preserved_after_sqlalchemy_recovery(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test oldest_ts is not reseeded from now after session recovery."""
    instance = get_instance(hass)
    entity_id = "sensor.oldest_ts_recovery"
    stable_entity_id = "sensor.oldest_ts_stable"

    hass.states.async_set(stable_entity_id, "on")
    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    oldest_ts_before_recovery = instance.states_manager.oldest_ts
    assert oldest_ts_before_recovery is not None

    freezer.tick(timedelta(seconds=1))
    start_time = dt_util.utcnow()

    event_session = instance.event_session
    assert event_session is not None

    with (
        patch("time.sleep"),
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(
                event_session,
                SQLAlchemyError("insert the state", "fake params", "forced to fail"),
            ),
        ),
    ):
        hass.states.async_set(entity_id, "fail")
        await async_wait_recording_done(hass)

    assert "SQLAlchemyError error processing task" in caplog.text

    freezer.tick(timedelta(seconds=1))
    hass.states.async_set(entity_id, "after")
    await async_wait_recording_done(hass)

    assert instance.states_manager.oldest_ts == oldest_ts_before_recovery

    with session_scope(hass=hass, read_only=True) as session:
        recorded_states = {row.state for row in session.query(States)}
    assert "fail" not in recorded_states

    hist = history.get_significant_states(
        hass,
        start_time,
        dt_util.utcnow(),
        entity_ids=[entity_id, stable_entity_id],
        include_start_time_state=True,
    )
    start_state = hist[entity_id][0]
    assert isinstance(start_state, State)
    assert start_state.state == "before"
    stable_start_state = hist[stable_entity_id][0]
    assert isinstance(stable_start_state, State)
    assert stable_start_state.state == "on"


@pytest.mark.parametrize(
    "flush_error",
    [
        pytest.param(
            OperationalError("insert the state", "fake params", "connection refused"),
            id="operational",
        ),
        pytest.param(
            InternalError("insert the state", "fake params", "server gone away"),
            id="internal",
        ),
        pytest.param(
            InterfaceError(
                "insert the state", "fake params", "connection already closed"
            ),
            id="interface",
        ),
    ],
)
@pytest.mark.usefixtures("recorder_mock")
async def test_recorder_retries_until_connection_restored(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    flush_error: OperationalError | InternalError | InterfaceError,
) -> None:
    """Test a mid-session connection loss keeps retrying instead of shutting down."""
    instance = get_instance(hass)
    entity_id = "sensor.reconnect_after_outage"

    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    oldest_ts_before_recovery = instance.states_manager.oldest_ts
    assert oldest_ts_before_recovery is not None
    assert instance.is_running

    event_session = instance.event_session
    assert event_session is not None

    original_restore = instance._restore_connection_tied_caches
    attempts = {"n": 0}

    def flaky_restore() -> None:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OperationalError("connect", {}, "connection refused")
        original_restore()

    with (
        patch("time.sleep"),
        patch.object(instance, "db_max_retries", 1),
        patch.object(instance, "db_retry_wait", 0),
        patch.object(
            instance, "_restore_connection_tied_caches", side_effect=flaky_restore
        ),
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(event_session, flush_error),
        ),
    ):
        hass.states.async_set(entity_id, "during_outage")
        await async_wait_recording_done(hass)

    assert attempts["n"] == 3
    assert instance.is_running
    assert "Recorder setup failed, recorder shutting down" not in caplog.text
    assert "Recorder database connection lost" in caplog.text
    assert "Recorder database connection restored" in caplog.text

    hass.states.async_set(entity_id, "after")
    await async_wait_recording_done(hass)

    assert instance.states_manager.oldest_ts == oldest_ts_before_recovery

    with session_scope(hass=hass, read_only=True) as session:
        recorded_states = {row.state for row in session.query(States)}
    assert "during_outage" not in recorded_states
    assert "before" in recorded_states
    assert "after" in recorded_states


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine", "recorder_mock")
@pytest.mark.parametrize("persistent_database", [True])
async def test_file_sqlite_reconnect_keeps_engine_and_history(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test file SQLite reconnect reloads caches without startup setup.

    Re-running `_setup_connection()` would call validate_or_move_away and can
    rename a locked healthy database to `.corrupt.*`.
    """
    instance = get_instance(hass)
    assert instance._uses_persistent_database()
    assert instance._using_file_sqlite
    assert instance._reconnect_disposes_engine() is False
    entity_id = "sensor.persistent_reconnect"

    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    oldest_ts_before_recovery = instance.states_manager.oldest_ts
    assert oldest_ts_before_recovery is not None
    engine_before = instance.engine
    assert engine_before is not None
    event_session = instance.event_session
    assert event_session is not None

    with (
        patch("time.sleep"),
        patch.object(instance, "db_max_retries", 1),
        patch.object(instance, "db_retry_wait", 0),
        patch.object(instance, "_close_connection") as close_connection,
        patch.object(instance, "_setup_connection") as setup_connection,
        patch(
            "homeassistant.components.recorder.core.validate_or_move_away_sqlite_database"
        ) as validate,
        patch.object(
            instance.states_manager,
            "load_from_db",
            wraps=instance.states_manager.load_from_db,
        ) as load_from_db,
        patch.object(
            instance.statistics_meta_manager,
            "load",
            wraps=instance.statistics_meta_manager.load,
        ) as load_statistics_meta,
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(
                event_session,
                OperationalError(
                    "insert the state", "fake params", "connection refused"
                ),
            ),
        ),
    ):
        hass.states.async_set(entity_id, "during_outage")
        await async_wait_recording_done(hass)

    close_connection.assert_not_called()
    setup_connection.assert_not_called()
    validate.assert_not_called()
    load_from_db.assert_called()
    load_statistics_meta.assert_called()
    assert instance.engine is engine_before
    assert instance.event_session is not None
    assert instance.event_session is not event_session
    assert instance._event_session_has_pending_writes is False
    assert instance.is_running
    assert "Recorder database connection lost" in caplog.text
    assert "Recorder database connection restored" in caplog.text

    hass.states.async_set(entity_id, "after")
    await async_wait_recording_done(hass)

    assert instance.states_manager.oldest_ts == oldest_ts_before_recovery

    def collect_states() -> set[str | None]:
        with session_scope(hass=hass, read_only=True) as session:
            return {row.state for row in session.query(States)}

    recorded_states = await instance.async_add_executor_job(collect_states)
    assert "during_outage" not in recorded_states
    assert "before" in recorded_states
    assert "after" in recorded_states


@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("recorder_mock")
async def test_persistent_reconnect_disposes_and_recreates_engine(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test remote reconnect disposes the engine and reloads from the same DB.

    On SQLite this patches `_using_file_sqlite` False so production
    `_close_connection` → `_setup_connection` → cache reload runs without
    validate/move. On mysql/postgresql that is already the production path.
    """
    instance = get_instance(hass)
    assert instance._uses_persistent_database()
    entity_id = "sensor.remote_reconnect"

    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    oldest_ts_before_recovery = instance.states_manager.oldest_ts
    assert oldest_ts_before_recovery is not None
    engine_before = instance.engine
    assert engine_before is not None
    event_session = instance.event_session
    assert event_session is not None

    with (
        patch("time.sleep"),
        patch.object(instance, "db_max_retries", 1),
        patch.object(instance, "db_retry_wait", 0),
        patch.object(
            Recorder, "_using_file_sqlite", new_callable=PropertyMock
        ) as using_file_sqlite,
        patch.object(
            instance, "_close_connection", wraps=instance._close_connection
        ) as close_connection,
        patch.object(
            instance, "_setup_connection", wraps=instance._setup_connection
        ) as setup_connection,
        patch(
            "homeassistant.components.recorder.core.validate_or_move_away_sqlite_database"
        ) as validate,
        patch.object(
            instance.states_manager,
            "load_from_db",
            wraps=instance.states_manager.load_from_db,
        ) as load_from_db,
        patch.object(
            instance.statistics_meta_manager,
            "load",
            wraps=instance.statistics_meta_manager.load,
        ) as load_statistics_meta,
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(
                event_session,
                OperationalError(
                    "insert the state", "fake params", "connection refused"
                ),
            ),
        ),
    ):
        using_file_sqlite.return_value = False
        hass.states.async_set(entity_id, "during_outage")
        await async_wait_recording_done(hass)

    close_connection.assert_called()
    setup_connection.assert_called()
    validate.assert_not_called()
    load_from_db.assert_called()
    load_statistics_meta.assert_called()
    assert instance.engine is not None
    assert instance.engine is not engine_before
    assert instance.event_session is not None
    assert instance.event_session is not event_session
    assert instance._event_session_has_pending_writes is False
    assert instance.is_running
    assert "Recorder database connection lost" in caplog.text
    assert "Recorder database connection restored" in caplog.text

    hass.states.async_set(entity_id, "after")
    await async_wait_recording_done(hass)

    assert instance.states_manager.oldest_ts == oldest_ts_before_recovery

    def collect_remote_states() -> set[str | None]:
        with session_scope(hass=hass, read_only=True) as session:
            return {row.state for row in session.query(States)}

    recorded_states = await instance.async_add_executor_job(collect_remote_states)
    assert "during_outage" not in recorded_states
    assert "before" in recorded_states
    assert "after" in recorded_states


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine", "recorder_mock")
@pytest.mark.parametrize("persistent_database", [True])
async def test_sqlite_lock_during_reconnect_does_not_move_database(
    hass: HomeAssistant,
) -> None:
    """Test a locked file SQLite database is not renamed .corrupt during reconnect."""
    instance = get_instance(hass)
    db_path = Path(dburl_to_path(instance.db_url))
    entity_id = "sensor.locked_reconnect"

    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    event_session = instance.event_session
    assert event_session is not None

    lock_cause = sqlite3.OperationalError("database is locked")
    flush_error = OperationalError("insert the state", {}, lock_cause)
    flush_error.__cause__ = lock_cause

    with (
        patch("time.sleep"),
        patch.object(instance, "db_max_retries", 1),
        patch.object(instance, "db_retry_wait", 0),
        patch.object(instance, "_setup_connection") as setup_connection,
        patch(
            "homeassistant.components.recorder.core.validate_or_move_away_sqlite_database"
        ) as validate,
        patch(
            "homeassistant.components.recorder.util.move_away_broken_database"
        ) as move_away,
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(event_session, flush_error),
        ),
    ):
        hass.states.async_set(entity_id, "during_outage")
        await async_wait_recording_done(hass)

    setup_connection.assert_not_called()
    validate.assert_not_called()
    move_away.assert_not_called()
    assert db_path.exists()
    assert not list(db_path.parent.glob(f"{db_path.name}.corrupt.*"))
    assert instance.is_running

    hass.states.async_set(entity_id, "after")
    await async_wait_recording_done(hass)

    def collect_states() -> set[str | None]:
        with session_scope(hass=hass, read_only=True) as session:
            return {row.state for row in session.query(States)}

    recorded_states = await instance.async_add_executor_job(collect_states)
    assert "during_outage" not in recorded_states
    assert "before" in recorded_states
    assert "after" in recorded_states


@pytest.mark.usefixtures("recorder_mock")
async def test_integrity_error_does_not_reconnect(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test IntegrityError rolls back the session instead of reconnecting."""
    instance = get_instance(hass)
    entity_id = "sensor.integrity_error"

    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    event_session = instance.event_session
    assert event_session is not None

    with (
        patch("time.sleep"),
        patch.object(instance, "_reconnect_database") as reconnect,
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(
                event_session,
                IntegrityError("insert the state", "fake params", "UNIQUE constraint"),
            ),
        ),
    ):
        hass.states.async_set(entity_id, "duplicate")
        await async_wait_recording_done(hass)

    reconnect.assert_not_called()
    assert instance._event_session_has_pending_writes is False
    assert "Recorder database connection lost" not in caplog.text
    assert "Unhandled database error while processing task" in caplog.text
    assert instance.is_running

    hass.states.async_set(entity_id, "after")
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        recorded_states = {row.state for row in session.query(States)}
    assert "duplicate" not in recorded_states
    assert "before" in recorded_states
    assert "after" in recorded_states


@pytest.mark.usefixtures("recorder_mock")
async def test_close_event_session_clears_pending_writes(
    hass: HomeAssistant,
) -> None:
    """Test _close_event_session resets the pending-writes flag."""
    instance = get_instance(hass)
    await async_wait_recording_done(hass)
    cleared: asyncio.Future[bool] = hass.loop.create_future()

    class ClearPendingWritesTask(RecorderTask):
        """Run session close on the recorder thread."""

        commit_before = False

        def run(self, instance: Recorder) -> None:
            instance._event_session_has_pending_writes = True
            instance._close_event_session()
            pending = instance._event_session_has_pending_writes
            instance._open_event_session()
            hass.loop.call_soon_threadsafe(cleared.set_result, pending is False)

    instance.queue_task(ClearPendingWritesTask())
    assert await cleared
    assert instance.event_session is not None
    assert instance._event_session_has_pending_writes is False


@pytest.mark.usefixtures("recorder_mock")
async def test_reconnect_stops_when_home_assistant_stops(
    hass: HomeAssistant,
) -> None:
    """Test reconnect retries do not block Home Assistant shutdown."""
    instance = get_instance(hass)
    entity_id = "sensor.reconnect_shutdown"

    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    event_session = instance.event_session
    assert event_session is not None
    entered = threading.Event()
    opens_while_stopping = {"n": 0}
    original_open = instance._open_event_session

    def never_restore() -> None:
        entered.set()
        raise OperationalError("connect", {}, "connection refused")

    def tracking_open() -> None:
        if instance.hass.is_stopping:
            opens_while_stopping["n"] += 1
        original_open()

    with (
        patch.object(instance, "db_max_retries", 1),
        patch.object(instance, "db_retry_wait", 0.05),
        patch.object(
            instance, "_restore_connection_tied_caches", side_effect=never_restore
        ),
        patch.object(instance, "_open_event_session", side_effect=tracking_open),
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(
                event_session,
                OperationalError(
                    "insert the state", "fake params", "connection refused"
                ),
            ),
        ),
    ):
        hass.states.async_set(entity_id, "during_outage")
        assert await hass.async_add_executor_job(entered.wait, 5)
        await hass.async_stop()

    assert not instance.is_running
    assert instance.event_session is None
    assert opens_while_stopping["n"] == 0


@pytest.mark.usefixtures("recorder_mock")
async def test_reconnect_success_after_stop_closes_session(
    hass: HomeAssistant,
) -> None:
    """Test a reconnect that succeeds after stop still closes the new session."""
    instance = get_instance(hass)
    entity_id = "sensor.reconnect_success_after_stop"

    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    event_session = instance.event_session
    assert event_session is not None
    entered = threading.Event()
    proceed = threading.Event()
    original_restore = instance._restore_connection_tied_caches

    def restore_after_stop() -> None:
        entered.set()
        assert proceed.wait(5)
        original_restore()

    def release_when_stopping() -> None:
        deadline = time.monotonic() + 5
        while not hass.is_stopping and time.monotonic() < deadline:
            time.sleep(0.01)
        proceed.set()

    with (
        patch.object(instance, "db_max_retries", 1),
        patch.object(instance, "db_retry_wait", 0),
        patch.object(
            instance, "_restore_connection_tied_caches", side_effect=restore_after_stop
        ),
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(
                event_session,
                OperationalError(
                    "insert the state", "fake params", "connection refused"
                ),
            ),
        ),
    ):
        hass.states.async_set(entity_id, "during_outage")
        assert await hass.async_add_executor_job(entered.wait, 5)
        releaser = threading.Thread(target=release_when_stopping, daemon=True)
        releaser.start()
        await hass.async_stop()
        releaser.join(5)

    assert not instance.is_running
    assert instance.event_session is None


@pytest.mark.usefixtures("recorder_mock")
async def test_unsupported_dialect_during_reconnect_stops_recorder(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test UnsupportedDialect during reconnect stops the recorder cleanly."""
    instance = get_instance(hass)
    entity_id = "sensor.reconnect_unsupported"

    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    event_session = instance.event_session
    assert event_session is not None

    def raise_unsupported() -> None:
        raise UnsupportedDialect

    def wait_stopped() -> bool:
        deadline = time.monotonic() + 5
        while instance.is_running and time.monotonic() < deadline:
            time.sleep(0.01)
        return not instance.is_running

    with (
        patch("time.sleep"),
        patch.object(instance, "db_max_retries", 1),
        patch.object(instance, "db_retry_wait", 0),
        patch.object(
            instance, "_restore_connection_tied_caches", side_effect=raise_unsupported
        ),
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(
                event_session,
                OperationalError(
                    "insert the state", "fake params", "connection refused"
                ),
            ),
        ),
    ):
        hass.states.async_set(entity_id, "during_outage")
        assert await hass.async_add_executor_job(wait_stopped)

    assert not instance.is_running
    assert instance.event_session is None
    assert "Unsupported database dialect during reconnect" in caplog.text


@pytest.mark.usefixtures("recorder_mock")
async def test_reconnect_reinitializes_event_listener_after_backlog(
    hass: HomeAssistant,
) -> None:
    """Test reconnect re-binds the event listener after backlog teardown.

    Live migration already calls `async_initialize` when `_event_listener` is
    None. A long mid-session outage can trip the same queue watcher.
    """
    instance = get_instance(hass)
    entity_id = "sensor.reconnect_listener"

    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)
    assert instance._event_listener is not None

    event_session = instance.event_session
    assert event_session is not None
    entered = threading.Event()
    proceed = threading.Event()
    original_restore = instance._restore_connection_tied_caches

    def restore_after_backlog() -> None:
        entered.set()
        assert proceed.wait(5)
        original_restore()

    with (
        patch.object(instance, "db_max_retries", 1),
        patch.object(instance, "db_retry_wait", 0),
        patch("homeassistant.components.recorder.core.MAX_QUEUE_BACKLOG_MIN_VALUE", 1),
        patch(
            "homeassistant.components.recorder.core.MIN_AVAILABLE_MEMORY_FOR_QUEUE_BACKLOG",
            sys.maxsize,
        ),
        patch.object(
            instance,
            "_restore_connection_tied_caches",
            side_effect=restore_after_backlog,
        ),
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(
                event_session,
                OperationalError(
                    "insert the state", "fake params", "connection refused"
                ),
            ),
        ),
    ):
        hass.states.async_set(entity_id, "during_outage")
        assert await hass.async_add_executor_job(entered.wait, 5)
        hass.states.async_set(entity_id, "queued")
        await hass.async_block_till_done()
        instance._async_check_queue()
        assert instance._event_listener is None
        proceed.set()
        await async_wait_recording_done(hass)

    assert instance._event_listener is not None
    assert instance.recording

    hass.states.async_set(entity_id, "after")
    await async_wait_recording_done(hass)

    def collect_listener_states() -> set[str | None]:
        with session_scope(hass=hass, read_only=True) as session:
            return {row.state for row in session.query(States)}

    recorded_states = await instance.async_add_executor_job(collect_listener_states)
    assert "during_outage" not in recorded_states
    assert "before" in recorded_states
    assert "after" in recorded_states


def test_uses_persistent_database_url() -> None:
    """Test in-memory SQLite is not treated as a persistent database."""
    method = Recorder._uses_persistent_database
    assert method(SimpleNamespace(db_url="sqlite://")) is False
    assert method(SimpleNamespace(db_url="sqlite:///:memory:")) is False
    assert method(SimpleNamespace(db_url="sqlite:///file:memdb1?mode=memory")) is False
    assert method(SimpleNamespace(db_url="postgresql://ha@db/homeassistant")) is True
    assert (
        method(SimpleNamespace(db_url="sqlite:////config/home-assistant_v2.db")) is True
    )


@pytest.mark.parametrize(
    ("db_url", "using_file_sqlite", "expected"),
    [
        pytest.param("sqlite://", False, False, id="memory"),
        pytest.param(
            "sqlite:////config/home-assistant_v2.db", True, False, id="file-sqlite"
        ),
        pytest.param("postgresql://ha@db/homeassistant", False, True, id="postgres"),
    ],
)
def test_reconnect_disposes_engine_only_for_remote_databases(
    db_url: str, using_file_sqlite: bool, expected: bool
) -> None:
    """Test file SQLite reconnect does not dispose; Postgres does."""
    ns = SimpleNamespace(db_url=db_url, _using_file_sqlite=using_file_sqlite)
    ns._uses_persistent_database = lambda: Recorder._uses_persistent_database(ns)
    assert Recorder._reconnect_disposes_engine(ns) is expected


def test_reconnect_wait_aborts_when_stopping() -> None:
    """Test reconnect backoff stops as soon as Home Assistant is stopping."""
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        recorder.hass.is_stopping = True

    recorder = SimpleNamespace(
        hass=SimpleNamespace(is_stopping=False), db_retry_wait=3.0
    )
    with patch("homeassistant.components.recorder.core.time.sleep", fake_sleep):
        Recorder._wait_for_reconnect_retry(recorder)

    assert sleeps == [0.5]


def test_reconnect_wait_slices_retry_interval() -> None:
    """Test reconnect backoff is split so shutdown can interrupt it."""
    sleeps: list[float] = []
    recorder = SimpleNamespace(
        hass=SimpleNamespace(is_stopping=False), db_retry_wait=1.2
    )
    with patch(
        "homeassistant.components.recorder.core.time.sleep",
        side_effect=sleeps.append,
    ):
        Recorder._wait_for_reconnect_retry(recorder)

    assert sleeps == pytest.approx([0.5, 0.5, 0.2])
