"""A pool for sqlite connections."""
import threading

from sqlalchemy.pool import NullPool, StaticPool


class RecorderPool(StaticPool, NullPool):
    """A hybird of NullPool and StaticPool.

    When called from the creating thread acts like StaticPool

    When called from any other thread, acts like NullPool
    """

    def __init__(self, *args, **kw):
        """Create the pool."""
        self._tid = threading.current_thread().ident
        StaticPool.__init__(self, *args, **kw)

    def status(self):
        """Status of the pool."""
        return "RecorderPool"

    def recreate(self):
        """Recreate the pool."""
        self.logger.info("Pool recreating")
        return self.__class__(
            self._creator,
            echo=self.echo,
            pre_ping=self._pre_ping,
            recycle=self._recycle,
            reset_on_return=self._reset_on_return,
            logging_name=self._orig_logging_name,
            _dispatch=self.dispatch,
            dialect=self._dialect,
        )

    def _do_return_conn(self, conn):
        if threading.current_thread().ident == self._tid:
            return super()._do_return_conn(conn)
        conn.close()

    def dispose(self):
        """Dispose of the connection."""
        if threading.current_thread().ident == self._tid:
            return super().dispose()

    def _do_get(self):
        if threading.current_thread().ident == self._tid:
            return super()._do_get()
        return super(NullPool, self)._create_connection()
