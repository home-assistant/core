"""Purge old data helper."""
from datetime import timedelta
import logging

import homeassistant.util.dt as dt_util

from .util import session_scope

_LOGGER = logging.getLogger(__name__)


def purge_old_data(instance, purge_days, repack):
    """Purge events and states older than purge_days ago."""
    from .models import States, Events

    purge_before = dt_util.utcnow() - timedelta(days=purge_days)
    _LOGGER.debug("Purging events before %s", purge_before)

    with session_scope(session=instance.get_session()) as session:
        deleted_rows = session.query(States) \
            .filter((States.last_updated < purge_before)) \
            .delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s states", deleted_rows)

        deleted_rows = session.query(Events) \
            .filter((Events.time_fired < purge_before)) \
            .delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s events", deleted_rows)

    # Execute sqlite vacuum command to free up space on disk
    _LOGGER.debug("DB engine driver: %s", instance.engine.driver)
    if repack and instance.engine.driver == 'pysqlite':
        from sqlalchemy import exc

        _LOGGER.debug("Vacuuming SQLite to free space")
        try:
            instance.engine.execute("VACUUM")
        except exc.OperationalError as err:
            _LOGGER.error("Error vacuuming SQLite: %s.", err)
