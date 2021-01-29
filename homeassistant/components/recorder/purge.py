"""Purge old data helper."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import time
from typing import TYPE_CHECKING

from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import distinct

from homeassistant.const import EVENT_STATE_CHANGED
import homeassistant.util.dt as dt_util

from .const import MAX_ROWS_TO_PURGE
from .models import Events, RecorderRuns, States
from .repack import repack_database
from .util import execute, session_scope

if TYPE_CHECKING:
    from . import Recorder

_LOGGER = logging.getLogger(__name__)

DEBUG_DATETIME_FMT = r"%Y-%m-%d %H:%M UTC"


def purge_old_data(
    instance: Recorder, purge_days: int, repack: bool, apply_filter: bool = False
) -> bool:
    """Purge events and states older than purge_days ago.

    Cleans up an timeframe of an hour, based on the oldest record.
    """
    purge_before = dt_util.utcnow() - timedelta(days=purge_days)
    _LOGGER.debug(
        "Purging states and events before target %s",
        purge_before.isoformat(sep=" ", timespec="seconds"),
    )
    try:
        with session_scope(session=instance.get_session()) as session:  # type: ignore
            # Purge a max of MAX_ROWS_TO_PURGE, based on the oldest states or events record
            event_ids = _select_event_ids_to_purge(session, purge_before)
            state_ids = _select_state_ids_to_purge(session, purge_before, event_ids)
            if state_ids:
                _purge_state_ids(session, state_ids)
            if event_ids:
                _purge_event_ids(session, event_ids)
                # If states or events purging isn't processing the purge_before yet,
                # return false, as we are not done yet.
                _LOGGER.debug("Purging hasn't fully completed yet")
                return False
            if apply_filter:
                if _purge_filtered_data(instance, session) is False:
                    return False
            _purge_old_recorder_runs(instance, session, purge_before)
        if repack:
            repack_database(instance)
    except OperationalError as err:
        # Retry when one of the following MySQL errors occurred:
        # 1205: Lock wait timeout exceeded; try restarting transaction
        # 1206: The total number of locks exceeds the lock table size
        # 1213: Deadlock found when trying to get lock; try restarting transaction
        if instance.engine.driver in ("mysqldb", "pymysql") and err.orig.args[0] in (
            1205,
            1206,
            1213,
        ):
            _LOGGER.info("%s; purge not completed, retrying", err.orig.args[1])
            time.sleep(instance.db_retry_wait)
            return False

        _LOGGER.warning("Error purging history: %s", err)
    except SQLAlchemyError as err:
        _LOGGER.warning("Error purging history: %s", err)
    return True


def _select_event_ids_to_purge(session: Session, purge_before: datetime) -> list[int]:
    """Return a list of event ids to purge."""
    events = (
        session.query(Events.event_id)
        .filter(Events.time_fired < purge_before)
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    _LOGGER.debug("Selected %s event ids to remove", len(events))
    return [event.event_id for event in events]


def _select_state_ids_to_purge(
    session: Session, purge_before: datetime, event_ids: list[int]
) -> list[int]:
    """Return a list of state ids to purge."""
    if not event_ids:
        return []
    states = (
        session.query(States.state_id)
        .filter(States.last_updated < purge_before)
        .filter(States.event_id.in_(event_ids))
        .all()
    )
    _LOGGER.debug("Selected %s state ids to remove", len(states))
    return [state.state_id for state in states]


def _purge_state_ids(session: Session, state_ids: list[int]) -> None:
    """Disconnect states and delete by state id."""

    # Update old_state_id to NULL before deleting to ensure
    # the delete does not fail due to a foreign key constraint
    # since some databases (MSSQL) cannot do the ON DELETE SET NULL
    # for us.
    disconnected_rows = (
        session.query(States)
        .filter(States.old_state_id.in_(state_ids))
        .update({"old_state_id": None}, synchronize_session=False)
    )
    _LOGGER.debug("Updated %s states to remove old_state_id", disconnected_rows)

    deleted_rows = (
        session.query(States)
        .filter(States.state_id.in_(state_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s states", deleted_rows)


def _purge_event_ids(session: Session, event_ids: list[int]) -> None:
    """Delete by event id."""
    deleted_rows = (
        session.query(Events)
        .filter(Events.event_id.in_(event_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s events", deleted_rows)


def _purge_old_recorder_runs(
    instance: Recorder, session: Session, purge_before: datetime
) -> None:
    """Purge all old recorder runs."""
    # Recorder runs is small, no need to batch run it
    deleted_rows = (
        session.query(RecorderRuns)
        .filter(RecorderRuns.start < purge_before)
        .filter(RecorderRuns.run_id != instance.run_info.run_id)
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s recorder_runs", deleted_rows)


def _purge_filtered_data(
    instance: Recorder,
    session: Session,
    *,
    batch_size_hours: int = 1,
) -> bool:
    """Purge filtered states and events that shouldn't be in database."""

    _LOGGER.debug("Purging filtered states and events")
    utc_now = dt_util.utcnow()
    batch_purge_before_states = utc_now
    batch_purge_before_events = utc_now

    # Check if excluded entity_ids are in database
    excluded_entity_ids: list[str] = [
        entity_id
        for (entity_id,) in session.query(distinct(States.entity_id)).all()
        if not instance.entity_filter(entity_id)
    ]

    if len(excluded_entity_ids) != 0:
        batch_purge_before_states = _purge_filtered_states(
            session,
            excluded_entity_ids,
            batch_purge_before_states,
            batch_size_hours,
        )

    # Check if excluded event_types are in database
    excluded_event_types: list[str] = [
        event_type
        for (event_type,) in session.query(distinct(Events.event_type)).all()
        if event_type in instance.exclude_t
    ]

    if len(excluded_event_types) != 0:
        batch_purge_before_events = _purge_filtered_events(
            session,
            excluded_event_types,
            batch_purge_before_events,
            batch_size_hours,
        )

    if batch_purge_before_states < utc_now or batch_purge_before_events < utc_now:
        _LOGGER.debug("Purging filter hasn't fully completed yet")
        return False

    return True


def _purge_filtered_states(
    session: Session,
    excluded_entity_ids: list[str],
    batch_purge_before: datetime,
    batch_size_hours: int,
) -> datetime:
    """Handle purging filtered states."""

    query = (
        session.query(States)
        .filter(States.entity_id.in_(excluded_entity_ids))
        .order_by(States.last_updated.asc())
        .limit(1)
    )
    states = execute(query, to_native=True, validate_entity_ids=False)  # type: ignore
    if states:
        batch_purge_before = states[0].last_updated + timedelta(hours=batch_size_hours)

    _LOGGER.debug(
        "Purging states before %s that should be filtered",
        batch_purge_before.strftime(DEBUG_DATETIME_FMT),
    )

    disconnected_rows = (
        session.query(States)
        .filter(
            States.old_state_id.in_(
                session.query(States.state_id)
                .filter(States.last_updated < batch_purge_before)
                .filter(States.entity_id.in_(excluded_entity_ids))
                .subquery()
            )
        )
        .update({"old_state_id": None}, synchronize_session=False)
    )
    _LOGGER.debug("Updated %s states to remove old_state_id", disconnected_rows)

    event_ids: list[int] = [
        event_id
        for (event_id,) in session.query(States.event_id)
        .filter(States.last_updated < batch_purge_before)
        .filter(States.event_id is not None)
        .filter(States.entity_id.in_(excluded_entity_ids))
        .all()
    ]

    deleted_rows_states = (
        session.query(States)
        .filter(States.last_updated < batch_purge_before)
        .filter(States.entity_id.in_(excluded_entity_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug(
        "Deleted %s states because entity_id is excluded", deleted_rows_states
    )

    if event_ids:
        deleted_rows_events = (
            session.query(Events)
            .filter(Events.event_type == EVENT_STATE_CHANGED)
            .filter(Events.time_fired < batch_purge_before)
            .filter(Events.event_id.in_(event_ids))
            .delete(synchronize_session=False)
        )
        _LOGGER.debug(
            "Deleted %s events because entity_id is excluded", deleted_rows_events
        )

    return batch_purge_before


def _purge_filtered_events(
    session: Session,
    excluded_event_types: list[str],
    batch_purge_before: datetime,
    batch_size_hours: int,
) -> datetime:
    """Handle purging filtered events."""

    query = (
        session.query(Events)
        .filter(Events.event_type.in_(excluded_event_types))
        .order_by(Events.time_fired.asc())
        .limit(1)
    )
    events = execute(query, to_native=True, validate_entity_ids=False)  # type: ignore
    if events:
        batch_purge_before = events[0].time_fired + timedelta(hours=batch_size_hours)

    _LOGGER.debug(
        "Purging events before %s the should be filtered",
        batch_purge_before.strftime(DEBUG_DATETIME_FMT),
    )

    event_ids: list[int] = [
        event_id
        for (event_id,) in session.query(Events.event_id)
        .filter(Events.time_fired < batch_purge_before)
        .join(States)
        .filter(Events.event_type.in_(excluded_event_types))
        .all()
    ]

    if event_ids:
        disconnected_rows = (
            session.query(States)
            .filter(
                States.old_state_id.in_(
                    session.query(States.state_id)
                    .filter(States.last_updated < batch_purge_before)
                    .filter(States.event_id.in_(event_ids))
                )
            )
            .update({"old_state_id": None}, synchronize_session=False)
        )

        deleted_rows_states = (
            session.query(States)
            .filter(States.last_updated < batch_purge_before)
            .filter(States.event_id.in_(event_ids))
            .delete(synchronize_session=False)
        )
        _LOGGER.debug("Updated %s states to remove old_state_id", disconnected_rows)
        _LOGGER.debug(
            "Deleted %s states because event_type is excluded", deleted_rows_states
        )

    deleted_rows_events = (
        session.query(Events)
        .filter(Events.time_fired < batch_purge_before)
        .filter(Events.event_type.in_(excluded_event_types))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug(
        "Deleted %s events because event_type is excluded", deleted_rows_events
    )

    return batch_purge_before
