"""Purge old data helper."""
from datetime import timedelta
import logging

import homeassistant.util.dt as dt_util

from .util import session_scope

_LOGGER = logging.getLogger(__name__)


def purge_old_data(instance, purge_days):
    """Purge events and states older than purge_days ago."""
    from .models import States, Events
    from sqlalchemy import orm
    from sqlalchemy.sql import exists

    purge_before = dt_util.utcnow() - timedelta(days=purge_days)

    with session_scope(session=instance.get_session()) as session:
        # For each entity, the most recent state is protected from deletion
        # s.t. we can properly restore state even if the entity has not been
        # updated in a long time
        states_alias = orm.aliased(States, name='StatesAlias')
        protected_states = session.query(States.state_id, States.event_id)\
            .filter(~exists()
                    .where(States.entity_id ==
                           states_alias.entity_id)
                    .where(states_alias.last_updated >
                           States.last_updated))\
            .all()

        protected_state_ids = tuple((state[0] for state in protected_states))
        protected_event_ids = tuple((state[1] for state in protected_states
                                     if state[1] is not None))

        deleted_rows = session.query(States) \
                              .filter((States.last_updated < purge_before)) \
                              .filter(~States.state_id.in_(
                                  protected_state_ids)) \
                              .delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s states", deleted_rows)

        # We also need to protect the events belonging to the protected states.
        # Otherwise, if the SQL server has "ON DELETE CASCADE" as default, it
        # will delete the protected state when deleting its associated
        # event. Also, we would be producing NULLed foreign keys otherwise.
        deleted_rows = session.query(Events) \
            .filter((Events.time_fired < purge_before)) \
            .filter(~Events.event_id.in_(
                protected_event_ids
            )) \
            .delete(synchronize_session=False)
        _LOGGER.debug("Deleted %s events", deleted_rows)

    # Execute sqlite vacuum command to free up space on disk
    _LOGGER.debug("DB engine driver: %s", instance.engine.driver)
    if instance.engine.driver == 'pysqlite' and not instance.did_vacuum:
        from sqlalchemy import exc

        _LOGGER.info("Vacuuming SQLite to free space")
        try:
            instance.engine.execute("VACUUM")
            instance.did_vacuum = True
        except exc.OperationalError as err:
            _LOGGER.error("Error vacuuming SQLite: %s.", err)
