"""A pool for sqlite connections."""
import threading
from typing import Any

from sqlalchemy.pool import NullPool, SingletonThreadPool

from homeassistant.helpers.frame import report

from .const import DB_WORKER_PREFIX

POOL_SIZE = 5


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
        if self.recorder_or_dbworker and self._conn and (conn := self._conn.current()):
            conn.close()

    def dispose(self) -> None:
        """Dispose of the connection."""
        if self.recorder_or_dbworker:
            super().dispose()

    # Any can be switched out for ConnectionPoolEntry in the next version of sqlalchemy
    def _do_get(self) -> Any:
        if self.recorder_or_dbworker:
            return super()._do_get()
        report(
            "accesses the database without the database executor; "
            "Use homeassistant.components.recorder.get_instance(hass).async_add_executor_job() "
            "for faster database operations",
            exclude_integrations={"recorder"},
            error_if_core=False,
        )
        return super(  # pylint: disable=bad-super-call
            NullPool, self
        )._create_connection()
