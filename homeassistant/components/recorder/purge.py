"""Purge old data helper."""
from datetime import timedelta
import logging
import time

from sqlalchemy.exc import OperationalError, SQLAlchemyError

import homeassistant.util.dt as dt_util

from .models import Events, RecorderRuns, States
from .util import session_scope

_LOGGER = logging.getLogger(__name__)

MAX_ROWS_TO_PURGE = 5000


def purge_old_data(instance, purge_days: int, repack: bool) -> bool:
    """Purge events and states older than purge_days ago.

    Cleans up an timeframe of an hour, based on the oldest record.
    """
    purge_before = dt_util.utcnow() - timedelta(days=purge_days)
    _LOGGER.debug("Purging states and events before target %s", purge_before)

    try:
        with session_scope(session=instance.get_session()) as session:
            # Purge a max of MAX_ROWS_TO_PURGE, based on the oldest states or events record
            event_ids = _select_event_ids_to_purge(session, purge_before)
            state_ids = _select_state_ids_to_purge(session, event_ids)
            if state_ids:
                _disconnect_states_about_to_be_purged(session, state_ids)
                _purge_state_ids(session, state_ids)
            if event_ids:
                _purge_event_ids(session, event_ids)
                # If states or events purging isn't processing the purge_before yet,
                # return false, as we are not done yet.
                _LOGGER.debug("Purging hasn't fully completed yet")
                return False
            _purge_old_recorder_runs(instance, session, purge_before)
        if repack:
            _repack_database(instance)
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


def _select_event_ids_to_purge(session, purge_before):
    """Return a list of event ids to purge."""
    events = (
        session.query(Events.event_id)
        .filter(Events.time_fired < purge_before)
        .limit(MAX_ROWS_TO_PURGE)
        .all()
    )
    _LOGGER.debug("Selected %s event ids to remove", len(events))
    return [event.event_id for event in events]


def _select_state_ids_to_purge(session, event_ids):
    """Return a list of state ids to purge."""
    states = session.query(States.state_id).filter(States.event_id.in_(event_ids)).all()
    _LOGGER.debug("Selected %s state ids to remove", len(states))
    return [state.state_id for state in states]


def _disconnect_states_about_to_be_purged(session, state_ids):
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


def _purge_state_ids(session, state_ids):
    """Delete by state id."""
    deleted_rows = (
        session.query(States)
        .filter(States.state_id.in_(state_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s states", deleted_rows)


def _purge_event_ids(session, event_ids):
    """Delete by event id."""
    deleted_rows = (
        session.query(Events)
        .filter(Events.event_id.in_(event_ids))
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s events", deleted_rows)


def _purge_old_recorder_runs(instance, session, purge_before):
    """Purge all old recorder runs."""
    # Recorder runs is small, no need to batch run it
    deleted_rows = (
        session.query(RecorderRuns)
        .filter(RecorderRuns.start < purge_before)
        .filter(RecorderRuns.run_id != instance.run_info.run_id)
        .delete(synchronize_session=False)
    )
    _LOGGER.debug("Deleted %s recorder_runs", deleted_rows)


def _repack_database(instance):
    """Repack based on engine type."""

    # Execute sqlite or postgresql vacuum command to free up space on disk
    if instance.engine.driver in ("pysqlite", "postgresql"):
        _LOGGER.debug("Vacuuming SQL DB to free space")
        instance.engine.execute("VACUUM")
        return

    # Optimize mysql / mariadb tables to free up space on disk
    if instance.engine.driver in ("mysqldb", "pymysql"):
        _LOGGER.debug("Optimizing SQL DB to free space")
        instance.engine.execute("OPTIMIZE TABLE states, events, recorder_runs")
        return
