"""Purge old data helper."""
from datetime import timedelta
import logging

import homeassistant.util.dt as dt_util

from .util import session_scope

_LOGGER = logging.getLogger(__name__)


def purge_old_data(instance, purge_days, timestamp=None):
    """Purge events and states older than purge_days ago."""
    from .models import States, Events, PurgeRun
    purge_before = dt_util.utcnow() - timedelta(days=purge_days)

    with session_scope(session=instance.get_session()) as session:
        deleted_rows = session.query(States) \
                              .filter((States.last_updated < purge_before)) \
                              .delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s states", deleted_rows)

        deleted_rows = session.query(Events) \
                              .filter((Events.time_fired < purge_before)) \
                              .delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s events", deleted_rows)

        if timestamp is not None:
            session.query(PurgeRun).delete(synchronize_session=False)
            session.add(PurgeRun(last=dt_util.as_utc(timestamp)))

    # Execute sqlite vacuum command to free up space on disk
    _LOGGER.debug("DB engine driver: %s", instance.engine.driver)
    if instance.engine.driver == 'pysqlite':
        _LOGGER.debug("Vacuuming SQLite to free space")
        instance.engine.execute("VACUUM")


def query_last_purge_time(instance):
    """Return the  timestamp of last scheduled purge or utcnow()."""
    from .models import PurgeRun

    with session_scope(session=instance.get_session()) as session:
        purge_run = session.query(PurgeRun).one_or_none()
        if purge_run is None:
            last = dt_util.utcnow()
            session.add(PurgeRun(last=last))
        else:
            last = dt_util.UTC.localize(purge_run.last)

    return dt_util.as_local(last)
