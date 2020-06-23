"""Purge old data helper."""
from datetime import timedelta
import logging

from sqlalchemy.exc import SQLAlchemyError

import homeassistant.util.dt as dt_util

from .models import Events, States
from .util import session_scope

_LOGGER = logging.getLogger(__name__)


def purge_old_data(instance, purge_days, repack):
    """Purge events and states older than purge_days ago."""
    purge_before = dt_util.utcnow() - timedelta(days=purge_days)
    _LOGGER.debug("Purging events before %s", purge_before)

    try:
        with session_scope(session=instance.get_session()) as session:
            deleted_rows = (
                session.query(States)
                .filter(States.last_updated < purge_before)
                .delete(synchronize_session=False)
            )
            _LOGGER.debug("Deleted %s states", deleted_rows)

            deleted_rows = (
                session.query(Events)
                .filter(Events.time_fired < purge_before)
                .delete(synchronize_session=False)
            )
            _LOGGER.debug("Deleted %s events", deleted_rows)

        if repack:
            # Execute sqlite or postgresql vacuum command to free up space on disk
            if instance.engine.driver in ("pysqlite", "postgresql"):
                _LOGGER.debug("Vacuuming SQL DB to free space")
                instance.engine.execute("VACUUM")
            # Optimize mysql / mariadb tables to free up space on disk
            elif instance.engine.driver == "mysqldb":
                _LOGGER.debug("Optimizing SQL DB to free space")
                instance.engine.execute("OPTIMIZE TABLE states, events")

    except SQLAlchemyError as err:
        _LOGGER.warning("Error purging history: %s.", err)
