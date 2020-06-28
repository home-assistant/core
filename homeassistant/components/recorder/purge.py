"""Purge old data helper."""
from datetime import timedelta
import logging

from sqlalchemy.exc import SQLAlchemyError

import homeassistant.util.dt as dt_util

from .models import Events, RecorderRuns, States
from .util import execute, session_scope

_LOGGER = logging.getLogger(__name__)


def purge_old_data(instance, purge_days: int, repack: bool) -> bool:
    """Purge events and states older than purge_days ago.

    Cleans up an timeframe of an hour, based on the oldest record.
    """
    purge_before = dt_util.utcnow() - timedelta(days=purge_days)
    _LOGGER.debug("Purging events before %s", purge_before)

    try:
        with session_scope(session=instance.get_session()) as session:
            query = session.query(States).order_by(States.last_updated.asc()).limit(1)
            states = execute(query, to_native=True, validate_entity_ids=False)

            states_purge_before = purge_before
            if states:
                states_purge_before = min(
                    purge_before, states[0].last_updated + timedelta(hours=1)
                )

            deleted_rows_states = (
                session.query(States)
                .filter(States.last_updated < states_purge_before)
                .delete(synchronize_session=False)
            )
            _LOGGER.debug("Deleted %s states", deleted_rows_states)

            query = session.query(Events).order_by(Events.time_fired.asc()).limit(1)
            events = execute(query, to_native=True)

            events_purge_before = purge_before
            if events:
                events_purge_before = min(
                    purge_before, events[0].time_fired + timedelta(hours=1)
                )

            deleted_rows_events = (
                session.query(Events)
                .filter(Events.time_fired < events_purge_before)
                .delete(synchronize_session=False)
            )
            _LOGGER.debug("Deleted %s events", deleted_rows_events)

            # If states or events purging isn't processing the purge_before yet,
            # return false, as we are not done yet.
            if (states_purge_before and states_purge_before != purge_before) or (
                events_purge_before and events_purge_before != purge_before
            ):
                _LOGGER.debug("Purging hasn't fully completed yet.")
                return False

            # Recorder runs is small, no need to batch run it
            deleted_rows = (
                session.query(RecorderRuns)
                .filter(RecorderRuns.start < purge_before)
                .delete(synchronize_session=False)
            )
            _LOGGER.debug("Deleted %s recorder_runs", deleted_rows)

        if repack:
            # Execute sqlite or postgresql vacuum command to free up space on disk
            if instance.engine.driver in ("pysqlite", "postgresql"):
                _LOGGER.debug("Vacuuming SQL DB to free space")
                instance.engine.execute("VACUUM")
            # Optimize mysql / mariadb tables to free up space on disk
            elif instance.engine.driver in ("mysqldb", "pymysql"):
                _LOGGER.debug("Optimizing SQL DB to free space")
                instance.engine.execute("OPTIMIZE TABLE states, events, recorder_runs")

    except SQLAlchemyError as err:
        _LOGGER.warning("Error purging history: %s.", err)

    return True
