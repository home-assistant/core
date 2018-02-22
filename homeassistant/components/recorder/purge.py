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
            .group_by(States.entity_id).all()

        protected_state_ids = tuple(state[0] for state in protected_states)

        if protected_state_ids:
            delete_states = delete_states \
                .filter(~States.state_id.in_(protected_state_ids))

        deleted_rows = delete_states.delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s states", deleted_rows)

        delete_events = session.query(Events) \
            .filter((Events.time_fired < purge_before))

        # We also need to protect the events belonging to the protected states.
        # Otherwise, if the SQL server has "ON DELETE CASCADE" as default, it
        # will delete the protected state when deleting its associated
        # event. Also, we would be producing NULLed foreign keys otherwise.
        if protected_state_ids:
            protected_events = session.query(States.event_id) \
                .filter(States.state_id.in_(protected_state_ids)) \
                .filter(States.event_id.isnot(None)) \
                .all()

            protected_event_ids = tuple(state[0] for state in protected_events)

            if protected_event_ids:
                delete_events = delete_events \
                    .filter(~Events.event_id.in_(protected_event_ids))

        deleted_rows = delete_events.delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s events", deleted_rows)

    # Execute sqlite vacuum command to free up space on disk
    _LOGGER.debug("DB engine driver: %s", instance.engine.driver)
    if repack and instance.engine.driver == 'pysqlite':
        from sqlalchemy import exc

        _LOGGER.debug("Vacuuming SQLite to free space")
        try:
            instance.engine.execute("VACUUM")
            instance.did_vacuum = True
        except exc.OperationalError as err:
            _LOGGER.error("Error vacuuming SQLite: %s.", err)
