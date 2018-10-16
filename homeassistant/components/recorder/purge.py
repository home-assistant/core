"""Purge old data helper."""
from datetime import timedelta
import logging

import homeassistant.util.dt as dt_util

from .util import session_scope

_LOGGER = logging.getLogger(__name__)


def purge_old_data(instance, purge_days, repack):
    """Purge events and states older than purge_days ago."""
    from .models import States, Events
    from sqlalchemy import func

    purge_before = dt_util.utcnow() - timedelta(days=purge_days)
    _LOGGER.debug("Purging events before %s", purge_before)

    with session_scope(session=instance.get_session()) as session:
        delete_states = session.query(States) \
                            .filter((States.last_updated < purge_before))

        # For each entity, the most recent state is protected from deletion
        # s.t. we can properly restore state even if the entity has not been
        # updated in a long time
        protected_states = session.query(func.max(States.state_id)) \
            .group_by(States.entity_id)

        # the following statement is a workaround of an issue of MySQL
        # that doesn't like subqueries with the same table name as in the
        # outer query when using delete, even not with aliases,
        # see https://github.com/home-assistant/home-assistant/pull/17084
        protected_states = session.query(protected_states.subquery())

        delete_states = delete_states \
            .filter(States.state_id.notin_(protected_states))

        deleted_rows = delete_states.delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s states", deleted_rows)

        delete_events = session.query(Events) \
            .filter((Events.time_fired < purge_before))

        # We also need to protect the events belonging to the protected states.
        # Otherwise, if the SQL server has "ON DELETE CASCADE" as default, it
        # will delete the protected state when deleting its associated
        # event. Also, we would be producing NULLed foreign keys otherwise.
        protected_events = session.query(States.event_id) \
            .filter(States.state_id.in_(protected_states)) \
            .filter(States.event_id.isnot(None))

        delete_events = delete_events \
            .filter(Events.event_id.notin_(protected_events))

        deleted_rows = delete_events.delete(synchronize_session=False)
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
