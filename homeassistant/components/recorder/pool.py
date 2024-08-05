"""A pool for sqlite connections."""

from __future__ import annotations

import asyncio
import logging
import threading
import traceback
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import (
    ConnectionPoolEntry,
    NullPool,
    SingletonThreadPool,
    StaticPool,
)

from homeassistant.helpers.frame import report
from homeassistant.util.loop import raise_for_blocking_call

_LOGGER = logging.getLogger(__name__)

# For debugging the MutexPool
DEBUG_MUTEX_POOL = True
DEBUG_MUTEX_POOL_TRACE = False

POOL_SIZE = 5

ADVISE_MSG = (
    "Use homeassistant.components.recorder.get_instance(hass).async_add_executor_job()"
)


class RecorderPool(SingletonThreadPool, NullPool):
    """A hybrid of NullPool and SingletonThreadPool.

    When called from the creating thread or db executor acts like SingletonThreadPool
    When called from any other thread, acts like NullPool
    """

    def __init__(  # pylint: disable=super-init-not-called
        self,
        creator: Any,
        recorder_and_worker_thread_ids: set[int] | None = None,
        **kw: Any,
    ) -> None:
        """Create the pool."""
        kw["pool_size"] = POOL_SIZE
        assert (
            recorder_and_worker_thread_ids is not None
        ), "recorder_and_worker_thread_ids is required"
        self.recorder_and_worker_thread_ids = recorder_and_worker_thread_ids
        SingletonThreadPool.__init__(self, creator, **kw)

    def recreate(self) -> RecorderPool:
        """Recreate the pool."""
        self.logger.info("Pool recreating")
        return self.__class__(
            self._creator,
            pool_size=self.size,
            recycle=self._recycle,
            echo=self.echo,
            pre_ping=self._pre_ping,
            logging_name=self._orig_logging_name,
            reset_on_return=self._reset_on_return,
            _dispatch=self.dispatch,
            dialect=self._dialect,
            recorder_and_worker_thread_ids=self.recorder_and_worker_thread_ids,
        )

    def _do_return_conn(self, record: ConnectionPoolEntry) -> None:
        if threading.get_ident() in self.recorder_and_worker_thread_ids:
            super()._do_return_conn(record)
            return
        record.close()

    def shutdown(self) -> None:
        """Close the connection."""
        if (
            threading.get_ident() in self.recorder_and_worker_thread_ids
            and self._conn
            and hasattr(self._conn, "current")
            and (conn := self._conn.current())
        ):
            conn.close()

    def dispose(self) -> None:
        """Dispose of the connection."""
        if threading.get_ident() in self.recorder_and_worker_thread_ids:
            super().dispose()

    def _do_get(self) -> ConnectionPoolEntry:  # type: ignore[return]
        if threading.get_ident() in self.recorder_and_worker_thread_ids:
            return super()._do_get()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # Not in an event loop but not in the recorder or worker thread
            # which is allowed but discouraged since its much slower
            return self._do_get_db_connection_protected()
        # In the event loop, raise an exception
        raise_for_blocking_call(
            self._do_get_db_connection_protected,
            strict=True,
            advise_msg=ADVISE_MSG,
        )
        # raise_for_blocking_call will raise an exception

    def _do_get_db_connection_protected(self) -> ConnectionPoolEntry:
        report(
            (
                "accesses the database without the database executor; "
                f"{ADVISE_MSG} "
                "for faster database operations"
            ),
            exclude_integrations={"recorder"},
            error_if_core=False,
        )
        return NullPool._create_connection(self)  # noqa: SLF001


class MutexPool(StaticPool):
    """A pool which prevents concurrent accesses from multiple threads.

    This is used in tests to prevent unsafe concurrent accesses to in-memory SQLite
    databases.
    """

    _reference_counter = 0
    pool_lock: threading.RLock

    def _do_return_conn(self, record: ConnectionPoolEntry) -> None:
        if DEBUG_MUTEX_POOL_TRACE:
            trace = traceback.extract_stack()
            trace_msg = "\n" + "".join(traceback.format_list(trace[:-1]))
        else:
            trace_msg = ""

        super()._do_return_conn(record)
        if DEBUG_MUTEX_POOL:
            self._reference_counter -= 1
            _LOGGER.debug(
                "%s return conn ctr: %s%s",
                threading.current_thread().name,
                self._reference_counter,
                trace_msg,
            )
        MutexPool.pool_lock.release()

    def _do_get(self) -> ConnectionPoolEntry:
        if DEBUG_MUTEX_POOL_TRACE:
            trace = traceback.extract_stack()
            trace_msg = "".join(traceback.format_list(trace[:-1]))
        else:
            trace_msg = ""

        if DEBUG_MUTEX_POOL:
            _LOGGER.debug("%s wait conn%s", threading.current_thread().name, trace_msg)
        # pylint: disable-next=consider-using-with
        got_lock = MutexPool.pool_lock.acquire(timeout=10)
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
