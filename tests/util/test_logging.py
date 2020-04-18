"""Test Home Assistant logging util methods."""
import asyncio
import logging
import threading

import homeassistant.util.logging as logging_util


def test_sensitive_data_filter():
    """Test the logging sensitive data filter."""
    log_filter = logging_util.HideSensitiveDataFilter("mock_sensitive")

    clean_record = logging.makeLogRecord({"msg": "clean log data"})
    log_filter.filter(clean_record)
    assert clean_record.msg == "clean log data"

    sensitive_record = logging.makeLogRecord({"msg": "mock_sensitive log"})
    log_filter.filter(sensitive_record)
    assert sensitive_record.msg == "******* log"


async def test_async_handler_loop_log(loop):
    """Test logging data inside from inside the event loop."""
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
    handler.name = "mock_name"
    assert base_handler.get_name() == "mock_name"

    log_record = logging.makeLogRecord({"msg": "Test Log Record"})
    handler.emit(log_record)
    await handler.async_close(True)
    assert queue.get_nowait().msg == "Test Log Record"
    assert queue.empty()


async def test_async_handler_thread_log(loop):
    """Test logging data from a thread."""
    loop._thread_ident = threading.get_ident()

    queue = asyncio.Queue(loop=loop)
    base_handler = logging.handlers.QueueHandler(queue)
    handler = logging_util.AsyncHandler(loop, base_handler)

    log_record = logging.makeLogRecord({"msg": "Test Log Record"})

    def add_log():
        """Emit a mock log."""
        handler.emit(log_record)
        handler.close()

    await loop.run_in_executor(None, add_log)
    await handler.async_close(True)

    assert queue.get_nowait().msg == "Test Log Record"
    assert queue.empty()


async def test_async_create_catching_coro(hass, caplog):
    """Test exception logging of wrapped coroutine."""

    async def job():
        raise Exception("This is a bad coroutine")

    hass.async_create_task(logging_util.async_create_catching_coro(job()))
    await hass.async_block_till_done()
    assert "This is a bad coroutine" in caplog.text
    assert "in test_async_create_catching_coro" in caplog.text
