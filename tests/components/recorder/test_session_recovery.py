"""Tests for recorder session recovery."""

from datetime import timedelta
from pathlib import Path
import sqlite3
from typing import Any
from unittest.mock import patch

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
from homeassistant.components.recorder.db_schema import States
from homeassistant.components.recorder.util import dburl_to_path, session_scope
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .common import async_wait_recording_done

from tests.typing import RecorderInstanceContextManager


def _connection_invalidated_error(
    exc_cls: type[OperationalError | InternalError | InterfaceError],
    message: str = "connection refused",
) -> OperationalError | InternalError | InterfaceError:
    """Build a DBAPIError that SQLAlchemy would mark as disconnect."""
    return exc_cls(
        "insert the state",
        "fake params",
        Exception(message),
        connection_invalidated=True,
    )


def _raise_if_state_in_session(event_session: Session, exception: Exception):
    """Return a flush side effect that fails once a States row is pending."""

    def _throw(*args, **kwargs):
        for obj in event_session:
            if isinstance(obj, States):
                raise exception

    return _throw


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


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

    def _throw_if_state_in_session(*args: Any, **kwargs: Any) -> None:
        for obj in event_session:
            if isinstance(obj, States):
                raise SQLAlchemyError(
                    "insert the state", "fake params", "forced to fail"
                )

    with (
        patch.object(
            event_session,
            "flush",
            side_effect=_throw_if_state_in_session,
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
        pytest.param(_connection_invalidated_error(OperationalError), id="operational"),
        pytest.param(
            _connection_invalidated_error(InternalError, "server gone away"),
            id="internal",
        ),
        pytest.param(
            _connection_invalidated_error(InterfaceError, "connection already closed"),
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
    assert "Recorder database connection lost" in caplog.text
    assert "Recorder database connection restored" in caplog.text
    hass.states.async_set(entity_id, "after")
    await async_wait_recording_done(hass)
    with session_scope(hass=hass, read_only=True) as session:
        recorded_states = {row.state for row in session.query(States)}
    assert "during_outage" not in recorded_states
    assert "before" in recorded_states
    assert "after" in recorded_states


@pytest.mark.skip_on_db_engine(["mysql", "postgresql"])
@pytest.mark.usefixtures("skip_by_db_engine", "recorder_mock")
@pytest.mark.parametrize("persistent_database", [True])
async def test_sqlite_lock_does_not_reconnect(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test SQLite lock errors stay on session recovery, not reconnect."""
    instance = get_instance(hass)
    db_path = Path(dburl_to_path(instance.db_url))
    entity_id = "sensor.locked_no_reconnect"
    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)
    event_session = instance.event_session
    assert event_session is not None
    lock_cause = sqlite3.OperationalError("database is locked")
    flush_error = OperationalError("insert the state", {}, lock_cause)
    flush_error.__cause__ = lock_cause
    assert flush_error.connection_invalidated is False
    with (
        patch("time.sleep"),
        patch.object(instance, "_reconnect_database") as reconnect,
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
        hass.states.async_set(entity_id, "during_lock")
        await async_wait_recording_done(hass)
    reconnect.assert_not_called()
    setup_connection.assert_not_called()
    validate.assert_not_called()
    move_away.assert_not_called()
    assert db_path.exists()
    assert "Recorder database connection lost" not in caplog.text


@pytest.mark.usefixtures("recorder_mock")
async def test_non_invalidated_operational_error_does_not_reconnect(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test OperationalError without connection_invalidated does not reconnect."""
    instance = get_instance(hass)
    entity_id = "sensor.deadlock_no_reconnect"
    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)
    event_session = instance.event_session
    assert event_session is not None
    flush_error = OperationalError(
        "insert the state",
        "fake params",
        Exception("Deadlock found when trying to get lock"),
    )
    assert flush_error.connection_invalidated is False
    with (
        patch("time.sleep"),
        patch.object(instance, "_reconnect_database") as reconnect,
        patch.object(
            event_session,
            "flush",
            side_effect=_raise_if_state_in_session(event_session, flush_error),
        ),
    ):
        hass.states.async_set(entity_id, "deadlock")
        await async_wait_recording_done(hass)
    reconnect.assert_not_called()
    assert "Recorder database connection lost" not in caplog.text


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
    assert "Recorder database connection lost" not in caplog.text
    assert "Unhandled database error while processing task" in caplog.text
