"""SQLAlchemy util functions."""
from contextlib import contextmanager
import logging
import time

from .const import DATA_INSTANCE

_LOGGER = logging.getLogger(__name__)

RETRIES = 3
QUERY_RETRY_WAIT = 0.1


@contextmanager
def session_scope(*, hass=None, session=None):
    """Provide a transactional scope around a series of operations."""
    if session is None and hass is not None:
        session = hass.data[DATA_INSTANCE].get_session()

    if session is None:
        raise RuntimeError('Session required')

    try:
        yield session
        session.commit()
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.error("Error executing query: %s", err)
        session.rollback()
        raise
    finally:
        session.close()


def commit(session, work):
    """Commit & retry work: Either a model or in a function."""
    import sqlalchemy.exc
    for _ in range(0, RETRIES):
        try:
            if callable(work):
                work(session)
            else:
                session.add(work)
            session.commit()
            return True
        except sqlalchemy.exc.OperationalError as err:
            _LOGGER.error("Error executing query: %s", err)
            session.rollback()
            time.sleep(QUERY_RETRY_WAIT)
    return False


def execute(qry):
    """Query the database and convert the objects to HA native form.

    This method also retries a few times in the case of stale connections.
    """
    from sqlalchemy.exc import SQLAlchemyError

    for tryno in range(0, RETRIES):
        try:
            return [
                row for row in
                (row.to_native() for row in qry)
                if row is not None]
        except SQLAlchemyError as err:
            _LOGGER.error("Error executing query: %s", err)

            if tryno == RETRIES - 1:
                raise
            else:
                time.sleep(QUERY_RETRY_WAIT)
