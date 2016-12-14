"""Logging utilities."""
import asyncio
import logging
import os
import threading

from .async import run_coroutine_threadsafe


class HideSensitiveDataFilter(logging.Filter):
    """Filter API password calls."""

    def __init__(self, text):
        """Initialize sensitive data filter."""
        super().__init__()
        self.text = text

    def filter(self, record):
        """Hide sensitive data in messages."""
        record.msg = record.msg.replace(self.text, '*******')

        return True


class AsyncLogFileHandler(logging.StreamHandler):
    def __init__(self, loop, filename, mode='a', encoding=None, delay=True):
        """Initialize async logging file handle."""
        self.base_filename = os.path.abspath(filename)
        self.mode = mode
        self.encoding = encoding
        self.loop = loop
        self._queue = asyncio.Queue(loop=loop)
        self._thread = threading.Thread(target=self._process)

        if delay:
            # pylint: disabled=non-parent-init-called
            logging.Handler.__init__(self)
            self.stream = None
        else:
            logging.StreamHandler.__init__(self, self._open())

    def start_thread(self):
        """Start thread for processing."""
        self._thread.start()

    def close(self):
        """Close stream and queue."""
        try:
            if self.stream:
                try:
                    self.flush()
                finally:
                    stream = self.stream
                    self.stream = None
                    if hasattr(stream, 'close'):
                        stream.close()
        finally:
            logging.StreamHandler.close(self)

    def _open(self):
        """Return file stream for handle."""
        return open(self.base_filename, self.mode, encoding=self.encoding)

    def emit(self, record):
        """Process a record."""
        ident = self.loop.__dict__.get("_thread_ident")

        # inside eventloop
        if ident is not None and ident == threading.get_ident():
            self.loop.call_soon(self._queue.put_nowait, record)
        # from a thread/executor
        else:
            self.loop.call_soon_threadsafe(self._queue.put_nowait, record)

    def __repr__(self):
        level = logging.getLevelName(self.level)
        return "<{} {} ({})>".format(
            self.__class__.__name__, self.base_filename, level)

    def _process(self):
        """Process log in a thread."""
        while True:
            data = run_coroutine_threadsafe(
                self._queue.get(), self.loop).result()
            if data is None:
                return

            if self.stream is None:
                self.stream = self._open()
            logging.StreamHandler.emit(self, data)
