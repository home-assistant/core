"""A pool for sqlite connections."""
import logging
import threading
import traceback
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool, SingletonThreadPool, StaticPool

from homeassistant.helpers.frame import report
from homeassistant.util.async_ import check_loop

from .const import DB_WORKER_PREFIX

_LOGGER = logging.getLogger(__name__)

# For debugging the MutexPool
DEBUG_MUTEX_POOL = True
DEBUG_MUTEX_POOL_TRACE = False

POOL_SIZE = 5

ADVISE_MSG = (
    "Use homeassistant.components.recorder.get_instance(hass).async_add_executor_job()"
)


class RecorderPool(SingletonThreadPool, NullPool):  # type: ignore[misc]
    """A hybrid of NullPool and SingletonThreadPool.

    When called from the creating thread or db executor acts like SingletonThreadPool
    When called from any other thread, acts like NullPool
    """

    def __init__(  # pylint: disable=super-init-not-called
        self, *args: Any, **kw: Any
    ) -> None:
        """Create the pool."""
        kw["pool_size"] = POOL_SIZE
        SingletonThreadPool.__init__(self, *args, **kw)

    @property
    def recorder_or_dbworker(self) -> bool:
        """Check if the thread is a recorder or dbworker thread."""
        thread_name = threading.current_thread().name
        return bool(
            thread_name == "Recorder" or thread_name.startswith(DB_WORKER_PREFIX)
        )

    # Any can be switched out for ConnectionPoolEntry in the next version of sqlalchemy
    def _do_return_conn(self, conn: Any) -> Any:
        if self.recorder_or_dbworker:
            return super()._do_return_conn(conn)
        conn.close()

    def shutdown(self) -> None:
        """Close the connection."""
        if (
            self.recorder_or_dbworker
            and self._conn
            and hasattr(self._conn, "current")
            and (conn := self._conn.current())
        ):
            conn.close()

    def dispose(self) -> None:
        """Dispose of the connection."""
        if self.recorder_or_dbworker:
            super().dispose()

    # Any can be switched out for ConnectionPoolEntry in the next version of sqlalchemy
    def _do_get(self) -> Any:
        if self.recorder_or_dbworker:
            return super()._do_get()
        check_loop(
            self._do_get_db_connection_protected,
            strict=True,
            advise_msg=ADVISE_MSG,
        )
        return self._do_get_db_connection_protected()

    def _do_get_db_connection_protected(self) -> Any:
        report(
            "accesses the database without the database executor; "
            f"{ADVISE_MSG} "
            "for faster database operations",
            exclude_integrations={"recorder"},
            error_if_core=False,
        )
        return super(NullPool, self)._create_connection()


class MutexPool(StaticPool):  # type: ignore[misc]
    """A pool which prevents concurrent accesses from multiple threads.

    This is used in tests to prevent unsafe concurrent accesses to in-memory SQLite
    databases.
    """

    _reference_counter = 0
    pool_lock: threading.RLock

    def _do_return_conn(self, conn: Any) -> None:
        if DEBUG_MUTEX_POOL_TRACE:
            trace = traceback.extract_stack()
            trace_msg = "\n" + "".join(traceback.format_list(trace[:-1]))
        else:
            trace_msg = ""

        super()._do_return_conn(conn)
        if DEBUG_MUTEX_POOL:
            self._reference_counter -= 1
            _LOGGER.debug(
                "%s return conn ctr: %s%s",
                threading.current_thread().name,
                self._reference_counter,
                trace_msg,
            )
        MutexPool.pool_lock.release()

    def _do_get(self) -> Any:

        if DEBUG_MUTEX_POOL_TRACE:
            trace = traceback.extract_stack()
            trace_msg = "".join(traceback.format_list(trace[:-1]))
        else:
            trace_msg = ""

        if DEBUG_MUTEX_POOL:
            _LOGGER.debug("%s wait conn%s", threading.current_thread().name, trace_msg)
        got_lock = MutexPool.pool_lock.acquire(timeout=1)
        if not got_lock:
            raise SQLAlchemyError
        conn = super()._do_get()
        if DEBUG_MUTEX_POOL:
            self._reference_counter += 1
            _LOGGER.debug(
                "%s get conn: ctr: %s",
                threading.current_thread().name,
                self._reference_counter,
            )
        return conn
