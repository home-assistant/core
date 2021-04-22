"""SQLAlchemy util functions."""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import timedelta
import logging
import os
import time

from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm.session import Session

from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.dt as dt_util

from .const import DATA_INSTANCE, SQLITE_URL_PREFIX
from .models import (
    ALL_TABLES,
    TABLE_RECORDER_RUNS,
    TABLE_SCHEMA_CHANGES,
    RecorderRuns,
    process_timestamp,
)

_LOGGER = logging.getLogger(__name__)

RETRIES = 3
QUERY_RETRY_WAIT = 0.1
SQLITE3_POSTFIXES = ["", "-wal", "-shm"]

# This is the maximum time after the recorder ends the session
# before we no longer consider startup to be a "restart" and we
# should do a check on the sqlite3 database.
MAX_RESTART_TIME = timedelta(minutes=10)


@contextmanager
def session_scope(
    *, hass: HomeAssistantType | None = None, session: Session | None = None
) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    if session is None and hass is not None:
        session = hass.data[DATA_INSTANCE].get_session()

    if session is None:
        raise RuntimeError("Session required")

    need_rollback = False
    try:
        yield session
        if session.get_transaction():
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


def validate_or_move_away_sqlite_database(dburl: str) -> bool:
    """Ensure that the database is valid or move it away."""
    dbpath = dburl_to_path(dburl)

    if not os.path.exists(dbpath):
        # Database does not exist yet, this is OK
        return True

    if not validate_sqlite_database(dbpath):
        move_away_broken_database(dbpath)
        return False

    return True


def dburl_to_path(dburl):
    """Convert the db url into a filesystem path."""
    return dburl[len(SQLITE_URL_PREFIX) :]


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
        if table in (TABLE_RECORDER_RUNS, TABLE_SCHEMA_CHANGES):
            cursor.execute(f"SELECT * FROM {table};")  # nosec # not injection
        else:
            cursor.execute(f"SELECT * FROM {table} LIMIT 1;")  # nosec # not injection

    return True


def validate_sqlite_database(dbpath: str) -> bool:
    """Run a quick check on an sqlite database to see if it is corrupt."""
    import sqlite3  # pylint: disable=import-outside-toplevel

    try:
        conn = sqlite3.connect(dbpath)
        run_checks_on_open_db(dbpath, conn.cursor())
        conn.close()
    except sqlite3.DatabaseError:
        _LOGGER.exception("The database at %s is corrupt or malformed", dbpath)
        return False

    return True


def run_checks_on_open_db(dbpath, cursor):
    """Run checks that will generate a sqlite3 exception if there is corruption."""
    sanity_check_passed = basic_sanity_check(cursor)
    last_run_was_clean = last_run_was_recently_clean(cursor)

    if sanity_check_passed and last_run_was_clean:
        _LOGGER.debug(
            "The system was restarted cleanly and passed the basic sanity check"
        )
        return

    if not sanity_check_passed:
        _LOGGER.warning(
            "The database sanity check failed to validate the sqlite3 database at %s",
            dbpath,
        )

    if not last_run_was_clean:
        _LOGGER.warning(
            "The system could not validate that the sqlite3 database at %s was shutdown cleanly",
            dbpath,
        )


def move_away_broken_database(dbfile: str) -> None:
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


def execute_on_connection(dbapi_connection, statement):
    """Execute a single statement with a dbapi connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute(statement)
    cursor.close()


def setup_connection_for_dialect(dialect_name, dbapi_connection):
    """Execute statements needed for dialect connection."""
    # Returns False if the the connection needs to be setup
    # on the next connection, returns True if the connection
    # never needs to be setup again.
    if dialect_name == "sqlite":
        old_isolation = dbapi_connection.isolation_level
        dbapi_connection.isolation_level = None
        execute_on_connection(dbapi_connection, "PRAGMA journal_mode=WAL")
        dbapi_connection.isolation_level = old_isolation
        # WAL mode only needs to be setup once
        # instead of every time we open the sqlite connection
        # as its persistent and isn't free to call every time.
        return True

    if dialect_name == "mysql":
        execute_on_connection(dbapi_connection, "SET session wait_timeout=28800")

    return False


def end_incomplete_runs(session, start_time):
    """End any incomplete recorder runs."""
    for run in session.query(RecorderRuns).filter_by(end=None):
        run.closed_incorrect = True
        run.end = start_time
        _LOGGER.warning(
            "Ended unfinished session (id=%s from %s)", run.run_id, run.start
        )
        session.add(run)
