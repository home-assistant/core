"""Test Home Assistant logging util methods."""
import asyncio
import logging
import threading

import homeassistant.util.logging as logging_util


@asyncio.coroutine
def test_sensitive_data_filter():
    """Test the logging sensitive data filter."""
    log_filter = logging_util.HideSensitiveDataFilter('mock_sensitive')

    clean_record = logging.makeLogRecord({'msg': "clean log data"})
    log_filter.filter(clean_record)
    assert clean_record.msg == "clean log data"

    sensitive_record = logging.makeLogRecord({'msg': "mock_sensitive log"})
    log_filter.filter(sensitive_record)
    assert sensitive_record.msg == "******* log"


@asyncio.coroutine
def test_async_handler_loop_log(loop):
    """Test the logging sensitive data filter."""
    loop._thread_ident = threading.get_ident()

    queue = asyncio.Queue(loop=loop)
    base_handler = logging.handlers.QueueHandler(queue)
    handler = logging_util.AsyncHandler(loop, base_handler)

    # Test passthrough props and noop functions
    assert handler.createLock() is None
    assert handler.acquire() is None
    assert handler.release() is None
    assert handler.formatter is base_handler.formatter
    assert handler.name is base_handler.get_name()
    handler.name = 'mock_name'
    assert base_handler.get_name() == 'mock_name'

    log_record = logging.makeLogRecord({'msg': "Test Log Record"})
    handler.emit(log_record)
    yield from handler.async_close(True)
    assert queue.get_nowait() == log_record
    assert queue.empty()


@asyncio.coroutine
def test_async_handler_thread_log(loop):
    """Test the logging sensitive data filter."""
    loop._thread_ident = threading.get_ident()

    queue = asyncio.Queue(loop=loop)
    base_handler = logging.handlers.QueueHandler(queue)
    handler = logging_util.AsyncHandler(loop, base_handler)

    log_record = logging.makeLogRecord({'msg': "Test Log Record"})

    def add_log():
        """Emit a mock log."""
        handler.emit(log_record)
        handler.close()

    yield from loop.run_in_executor(None, add_log)
    yield from handler.async_close(True)

    assert queue.get_nowait() == log_record
    assert queue.empty()
