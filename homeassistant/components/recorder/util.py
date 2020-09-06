"""SQLAlchemy util functions."""
from contextlib import contextmanager
from datetime import timedelta
import logging
import os
import time

from sqlalchemy.exc import OperationalError, SQLAlchemyError

import homeassistant.util.dt as dt_util

from .const import CONF_DB_INTEGRITY_CHECK, DATA_INSTANCE, SQLITE_URL_PREFIX
from .models import ALL_TABLES, process_timestamp

_LOGGER = logging.getLogger(__name__)

RETRIES = 3
QUERY_RETRY_WAIT = 0.1
SQLITE3_POSTFIXES = ["", "-wal", "-shm"]

# This is the maximum time after the recorder ends the session
# before we no longer consider startup to be a "restart" and we
# should do a check on the sqlite3 database.
MAX_RESTART_TIME = timedelta(minutes=10)


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
                        "querying %d rows took %fs",
                        len(result),
                        elapsed,
                    )

            return result
        except SQLAlchemyError as err:
            _LOGGER.error("Error executing query: %s", err)

            if tryno == RETRIES - 1:
                raise
            time.sleep(QUERY_RETRY_WAIT)


def validate_or_move_away_sqlite_database(dburl: str, db_integrity_check: bool) -> bool:
    """Ensure that the database is valid or move it away."""
    dbpath = dburl[len(SQLITE_URL_PREFIX) :]

    if not os.path.exists(dbpath):
        # Database does not exist yet, this is OK
        return True

    if not validate_sqlite_database(dbpath, db_integrity_check):
        _move_away_broken_database(dbpath)
        return False

    return True


def last_run_was_recently_clean(cursor):
    """Verify the last recorder run was recently clean."""

    cursor.execute("SELECT end FROM recorder_runs ORDER BY start DESC LIMIT 1;")
    end_time = cursor.fetchone()

    if not end_time or not end_time[0]:
        return False

    last_run_end_time = process_timestamp(dt_util.parse_datetime(end_time[0]))
    now = dt_util.utcnow()

    _LOGGER.debug("The last run ended at: %s (now: %s)", last_run_end_time, now)

    if last_run_end_time + MAX_RESTART_TIME < now:
        return False

    return True


def basic_sanity_check(cursor):
    """Check tables to make sure select does not fail."""

    for table in ALL_TABLES:
        cursor.execute(f"SELECT * FROM {table} LIMIT 1;")  # sec: not injection

    return True


def validate_sqlite_database(dbpath: str, db_integrity_check: bool) -> bool:
    """Run a quick check on an sqlite database to see if it is corrupt."""
    import sqlite3  # pylint: disable=import-outside-toplevel

    try:
        conn = sqlite3.connect(dbpath)
        run_checks_on_open_db(dbpath, conn.cursor(), db_integrity_check)
        conn.close()
    except sqlite3.DatabaseError:
        _LOGGER.exception("The database at %s is corrupt or malformed.", dbpath)
        return False

    return True


def run_checks_on_open_db(dbpath, cursor, db_integrity_check):
    """Run checks that will generate a sqlite3 exception if there is corruption."""
    if basic_sanity_check(cursor) and last_run_was_recently_clean(cursor):
        _LOGGER.debug(
            "The quick_check will be skipped as the system was restarted cleanly and passed the basic sanity check"
        )
        return

    if not db_integrity_check:
        # Always warn so when it does fail they remember it has
        # been manually disabled
        _LOGGER.warning(
            "The quick_check on the sqlite3 database at %s was skipped because %s was disabled",
            dbpath,
            CONF_DB_INTEGRITY_CHECK,
        )
        return

    _LOGGER.debug(
        "A quick_check is being performed on the sqlite3 database at %s", dbpath
    )
    cursor.execute("PRAGMA QUICK_CHECK")


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
