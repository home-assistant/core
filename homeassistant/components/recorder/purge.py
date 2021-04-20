"""Purge old data helper."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import time
from typing import TYPE_CHECKING

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import distinct

import homeassistant.util.dt as dt_util

from .const import MAX_ROWS_TO_PURGE
from .models import Events, RecorderRuns, States
from .repack import repack_database
from .util import session_scope

if TYPE_CHECKING:
    from . import Recorder

_LOGGER = logging.getLogger(__name__)

# Retry when one of the following MySQL errors occurred:
RETRYABLE_MYSQL_ERRORS = (1205, 1206, 1213)
# 1205: Lock wait timeout exceeded; try restarting transaction
# 1206: The total number of locks exceeds the lock table size
# 1213: Deadlock found when trying to get lock; try restarting transaction


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
            if apply_filter and _purge_filtered_data(instance, session) is False:
                _LOGGER.debug("Cleanup filtered data hasn't fully completed yet")
                return False
            _purge_old_recorder_runs(instance, session, purge_before)
        if repack:
            repack_database(instance)
    except OperationalError as err:
        if (
            instance.engine.dialect.name == "mysql"
            and err.orig.args[0] in RETRYABLE_MYSQL_ERRORS
        ):
            _LOGGER.info("%s; purge not completed, retrying", err.orig.args[1])
            time.sleep(instance.db_retry_wait)
            return False

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


def _purge_filtered_data(instance: Recorder, session: Session) -> bool:
    """Remove filtered states and events that shouldn't be in the database."""
    _LOGGER.debug("Cleanup filtered data")

    # Check if excluded entity_ids are in database
    excluded_entity_ids: list[str] = [
        entity_id
        for (entity_id,) in session.query(distinct(States.entity_id)).all()
        if not instance.entity_filter(entity_id)
    ]
    if len(excluded_entity_ids) > 0:
        _purge_filtered_states(session, excluded_entity_ids)
        return False

    # Check if excluded event_types are in database
    excluded_event_types: list[str] = [
        event_type
        for (event_type,) in session.query(distinct(Events.event_type)).all()
        if event_type in instance.exclude_t
    ]
    if len(excluded_event_types) > 0:
        _purge_filtered_events(session, excluded_event_types)
        return False

    return True


def _purge_filtered_states(session: Session, excluded_entity_ids: list[str]) -> None:
    """Remove filtered states and linked events."""
    state_ids: list[int]
    event_ids: list[int | None]
    state_ids, event_ids = zip(
        *(
            session.query(States.state_id, States.event_id)
            .filter(States.entity_id.in_(excluded_entity_ids))
            .limit(MAX_ROWS_TO_PURGE)
            .all()
        )
    )
    event_ids = [id_ for id_ in event_ids if id_ is not None]
    _LOGGER.debug(
        "Selected %s state_ids to remove that should be filtered", len(state_ids)
    )
    _purge_state_ids(session, state_ids)
    _purge_event_ids(session, event_ids)  # type: ignore  # type of event_ids already narrowed to 'list[int]'


def _purge_filtered_events(session: Session, excluded_event_types: list[str]) -> None:
    """Remove filtered events and linked states."""
    events: list[Events] = (
        session.query(Events.event_id)
        .filter(Events.event_type.in_(excluded_event_types))
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    event_ids: list[int] = [event.event_id for event in events]
    _LOGGER.debug(
        "Selected %s event_ids to remove that should be filtered", len(event_ids)
    )
    states: list[States] = (
        session.query(States.state_id).filter(States.event_id.in_(event_ids)).all()
    )
    state_ids: list[int] = [state.state_id for state in states]
    _purge_state_ids(session, state_ids)
    _purge_event_ids(session, event_ids)
