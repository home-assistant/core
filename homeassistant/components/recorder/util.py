"""SQLAlchemy util functions."""
from contextlib import contextmanager
import logging
import os
import time

from sqlalchemy.exc import OperationalError, SQLAlchemyError

import homeassistant.util.dt as dt_util

from .const import DATA_INSTANCE, SQLITE_URL_PREFIX

_LOGGER = logging.getLogger(__name__)

RETRIES = 3
QUERY_RETRY_WAIT = 0.1
SQLITE3_POSTFIXES = ["", "-wal", "-shm"]


@contextmanager
def session_scope(*, hass=None, session=None):
    """Provide a transactional scope around a series of operations."""
    if session is None and hass is not None:
        session = hass.data[DATA_INSTANCE].get_session()

    if session is None:
        raise RuntimeError("Session required")

    need_rollback = False
    try:
        yield session
        if session.transaction:
            need_rollback = True
            session.commit()
    except Exception as err:
        _LOGGER.error("Error executing query: %s", err)
        if need_rollback:
            session.rollback()
        raise
    finally:
        session.close()


def commit(session, work):
    """Commit & retry work: Either a model or in a function."""
    for _ in range(0, RETRIES):
        try:
            if callable(work):
                work(session)
            else:
                session.add(work)
            session.commit()
            return True
        except OperationalError as err:
            _LOGGER.error("Error executing query: %s", err)
            session.rollback()
            time.sleep(QUERY_RETRY_WAIT)
    return False


def execute(qry, to_native=False, validate_entity_ids=True):
    """Query the database and convert the objects to HA native form.

    This method also retries a few times in the case of stale connections.
    """

    for tryno in range(0, RETRIES):
        try:
            timer_start = time.perf_counter()
            if to_native:
                result = [
                    row
                    for row in (
                        row.to_native(validate_entity_id=validate_entity_ids)
                        for row in qry
                    )
                    if row is not None
                ]
            else:
                result = list(qry)

            if _LOGGER.isEnabledFor(logging.DEBUG):
                elapsed = time.perf_counter() - timer_start
                if to_native:
                    _LOGGER.debug(
                        "converting %d rows to native objects took %fs",
                        len(result),
                        elapsed,
                    )
                else:
                    _LOGGER.debug(
                        "querying %d rows took %fs", len(result), elapsed,
                    )

            return result
        except SQLAlchemyError as err:
            _LOGGER.error("Error executing query: %s", err)

            if tryno == RETRIES - 1:
                raise
            time.sleep(QUERY_RETRY_WAIT)


def validate_or_move_away_sqlite_database(dburl: str) -> bool:
    """Ensure that the database is valid or move it away."""
    dbpath = dburl[len(SQLITE_URL_PREFIX) :]

    if not os.path.exists(dbpath):
        # Database does not exist yet, this is OK
        return True

    if not validate_sqlite_database(dbpath):
        _move_away_broken_database(dbpath)
        return False

    return True


def validate_sqlite_database(dbpath: str) -> bool:
    """Run a quick check on an sqlite database to see if it is corrupt."""
    import sqlite3  # pylint: disable=import-outside-toplevel

    try:
        conn = sqlite3.connect(dbpath)
        conn.cursor().execute("PRAGMA QUICK_CHECK")
        conn.close()
    except sqlite3.DatabaseError:
        _LOGGER.exception("The database at %s is corrupt or malformed.", dbpath)
        return False

    return True


def _move_away_broken_database(dbfile: str) -> None:
    """Move away a broken sqlite3 database."""

    isotime = dt_util.utcnow().isoformat()
    corrupt_postfix = f".corrupt.{isotime}"

    _LOGGER.error(
        "The system will rename the corrupt database file %s to %s in order to allow startup to proceed",
        dbfile,
        f"{dbfile}{corrupt_postfix}",
    )

    for postfix in SQLITE3_POSTFIXES:
        path = f"{dbfile}{postfix}"
        if not os.path.exists(path):
            continue
        os.rename(path, f"{path}{corrupt_postfix}")
