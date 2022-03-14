"""A pool for sqlite connections."""
import logging
import threading

from sqlalchemy.pool import NullPool, SingletonThreadPool

POOL_SIZE = 5
_LOGGER = logging.getLogger(__name__)


class RecorderPool(SingletonThreadPool, NullPool):
    """A hybrid of NullPool and SingletonThreadPool.

    When called from the creating thread or db executor acts like SingletonThreadPool
    When called from any other thread, acts like NullPool
    """

    def __init__(self, *args, **kw):  # pylint: disable=super-init-not-called
        """Create the pool."""
        kw["pool_size"] = POOL_SIZE
        SingletonThreadPool.__init__(self, *args, **kw)

    @property
    def recorder_or_dbworker(self) -> bool:
        """Check if the thread is a recorder or dbworker thread."""
        thread_name = threading.current_thread().name
        return bool(thread_name == "Recorder" or thread_name.startswith("DbWorker"))

    def _do_return_conn(self, conn):
        if self.recorder_or_dbworker:
            return super()._do_return_conn(conn)
        conn.close()

    def shutdown(self):
        """Close the connection."""
        if self.recorder_or_dbworker and (conn := self._conn.current()):
            conn.close()

    def dispose(self):
        """Dispose of the connection."""
        if self.recorder_or_dbworker:
            return super().dispose()

    def _do_get(self):
        if self.recorder_or_dbworker:
            return super()._do_get()
        _LOGGER.warning(
            "Database access is slower in the default executor, "
            "use homeassistant.components.recorder.get_instance(hass).async_add_executor_job() "
            "for database operations"
        )
        return super(  # pylint: disable=bad-super-call
            NullPool, self
        )._create_connection()
