"""Test Home Assistant logging util methods."""

import asyncio
from functools import partial
import logging
import queue
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import (
    HomeAssistant,
    callback,
    is_callback,
    is_callback_check_partial,
)
from homeassistant.util import logging as logging_util


async def empty_log_queue() -> None:
    """Empty the log queue."""
    log_queue: queue.SimpleQueue = logging.root.handlers[0].queue
    while not log_queue.empty():
        await asyncio.sleep(0)


async def test_logging_with_queue_handler() -> None:
    """Test logging with HomeAssistantQueueHandler."""

    simple_queue = queue.SimpleQueue()
    handler = logging_util.HomeAssistantQueueHandler(simple_queue)

    log_record = logging.makeLogRecord({"msg": "Test Log Record"})

    handler.emit(log_record)

    with (
        pytest.raises(asyncio.CancelledError),
        patch.object(handler, "enqueue", side_effect=asyncio.CancelledError),
    ):
        handler.emit(log_record)

    with patch.object(handler, "emit") as emit_mock:
        handler.handle(log_record)
        emit_mock.assert_called_once()

    with (
        patch.object(handler, "filter") as filter_mock,
        patch.object(handler, "emit") as emit_mock,
    ):
        filter_mock.return_value = False
        handler.handle(log_record)
        emit_mock.assert_not_called()

    with (
        patch.object(handler, "enqueue", side_effect=OSError),
        patch.object(handler, "handleError") as mock_handle_error,
    ):
        handler.emit(log_record)
        mock_handle_error.assert_called_once()

    handler.close()

    assert simple_queue.get_nowait().msg == "Test Log Record"
    assert simple_queue.empty()


async def test_migrate_log_handler(hass: HomeAssistant) -> None:
    """Test migrating log handlers."""

    logging_util.async_activate_log_queue_handler(hass)

    assert len(logging.root.handlers) == 1
    assert isinstance(logging.root.handlers[0], logging_util.HomeAssistantQueueHandler)

    # Test that the close hook shuts down the queue handler's thread
    listener_thread = logging.root.handlers[0].listener._thread
    assert listener_thread.is_alive()
    logging.root.handlers[0].close()
    assert not listener_thread.is_alive()


@pytest.mark.no_fail_on_log_exception
async def test_async_create_catching_coro(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test exception logging of wrapped coroutine."""

    async def job():
        raise Exception("This is a bad coroutine")  # noqa: TRY002

    hass.async_create_task(logging_util.async_create_catching_coro(job()))
    await hass.async_block_till_done()
    assert "This is a bad coroutine" in caplog.text
    assert "in test_async_create_catching_coro" in caplog.text


def test_catch_log_exception() -> None:
    """Test it is still a callback after wrapping including partial."""

    async def async_meth():
        pass

    assert asyncio.iscoroutinefunction(
        logging_util.catch_log_exception(partial(async_meth), lambda: None)
    )

    @callback
    def callback_meth():
        pass

    assert is_callback_check_partial(
        logging_util.catch_log_exception(partial(callback_meth), lambda: None)
    )

    def sync_meth():
        pass

    wrapped = logging_util.catch_log_exception(partial(sync_meth), lambda: None)

    assert not is_callback(wrapped)
    assert not asyncio.iscoroutinefunction(wrapped)


@pytest.mark.no_fail_on_log_exception
async def test_catch_log_exception_catches_and_logs() -> None:
    """Test it is still a callback after wrapping including partial."""
    saved_args = []

    def save_args(*args):
        saved_args.append(args)

    async def async_meth():
        raise ValueError("failure async")

    func = logging_util.catch_log_exception(async_meth, save_args)
    await func("failure async passed")

    assert saved_args == [("failure async passed",)]
    saved_args.clear()

    @callback
    def callback_meth():
        raise ValueError("failure callback")

    func = logging_util.catch_log_exception(callback_meth, save_args)
    func("failure callback passed")

    assert saved_args == [("failure callback passed",)]
    saved_args.clear()

    def sync_meth():
        raise ValueError("failure sync")

    func = logging_util.catch_log_exception(sync_meth, save_args)
    func("failure sync passed")

    assert saved_args == [("failure sync passed",)]


@patch("homeassistant.util.logging.HomeAssistantQueueListener.MAX_LOGS_COUNT", 5)
@patch(
    "homeassistant.util.logging.HomeAssistantQueueListener.EXCLUDED_LOG_COUNT_MODULES",
    ["excluded"],
)
@pytest.mark.parametrize(
    (
        "logger1_count",
        "logger1_expected_notices",
        "logger2_count",
        "logger2_expected_notices",
    ),
    [(4, 0, 0, 0), (5, 1, 1, 0), (11, 1, 5, 1), (20, 1, 20, 1)],
)
async def test_noisy_loggers(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    logger1_count: int,
    logger1_expected_notices: int,
    logger2_count: int,
    logger2_expected_notices: int,
) -> None:
    """Test that noisy loggers all logged as warnings."""

    logging_util.async_activate_log_queue_handler(hass)
    logger1 = logging.getLogger("noisy1")
    logger2 = logging.getLogger("noisy2.module")
    logger_excluded = logging.getLogger("excluded.module")

    for _ in range(logger1_count):
        logger1.info("This is a log")

    for _ in range(logger2_count):
        logger2.info("This is another log")

    for _ in range(logging_util.HomeAssistantQueueListener.MAX_LOGS_COUNT + 1):
        logger_excluded.info("This log should not trigger a warning")

    await empty_log_queue()

    assert (
        caplog.text.count(
            "Module noisy1 is logging too frequently. 5 messages since last count"
        )
        == logger1_expected_notices
    )
    assert (
        caplog.text.count(
            "Module noisy2.module is logging too frequently. 5 messages since last count"
        )
        == logger2_expected_notices
    )
    # Ensure that the excluded module did not trigger a warning
    assert (
        caplog.text.count("is logging too frequently")
        == logger1_expected_notices + logger2_expected_notices
    )

    # close the handler so the queue thread stops
    logging.root.handlers[0].close()


@patch("homeassistant.util.logging.HomeAssistantQueueListener.MAX_LOGS_COUNT", 1)
async def test_noisy_loggers_ignores_self(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that the noisy loggers warning does not trigger a warning for its own module."""

    logging_util.async_activate_log_queue_handler(hass)
    logger1 = logging.getLogger("noisy_module1")
    logger2 = logging.getLogger("noisy_module2")
    logger3 = logging.getLogger("noisy_module3")

    logger1.info("This is a log")
    logger2.info("This is a log")
    logger3.info("This is a log")

    await empty_log_queue()
    assert caplog.text.count("logging too frequently") == 3

    # close the handler so the queue thread stops
    logging.root.handlers[0].close()


@patch("homeassistant.util.logging.HomeAssistantQueueListener.MAX_LOGS_COUNT", 5)
async def test_noisy_loggers_ignores_lower_than_info(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that noisy loggers all logged as warnings, except for levels lower than INFO."""

    logging_util.async_activate_log_queue_handler(hass)
    logger = logging.getLogger("noisy_module")

    for _ in range(5):
        logger.debug("This is a log")

    await empty_log_queue()
    expected_warning = "Module noisy_module is logging too frequently"
    assert caplog.text.count(expected_warning) == 0

    logger.info("This is a log")
    logger.info("This is a log")
    logger.warning("This is a log")
    logger.error("This is a log")
    logger.critical("This is a log")

    await empty_log_queue()
    assert caplog.text.count(expected_warning) == 1

    # close the handler so the queue thread stops
    logging.root.handlers[0].close()


@patch("homeassistant.util.logging.HomeAssistantQueueListener.MAX_LOGS_COUNT", 3)
async def test_noisy_loggers_counters_reset(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that noisy logger counters reset periodically."""

    logging_util.async_activate_log_queue_handler(hass)
    logger = logging.getLogger("noisy_module")

    expected_warning = "Module noisy_module is logging too frequently"

    # Do multiple iterations to ensure the reset is periodic
    for _ in range(logging_util.HomeAssistantQueueListener.MAX_LOGS_COUNT * 2):
        logger.info("This is log 0")
        await empty_log_queue()

        freezer.tick(
            logging_util.HomeAssistantQueueListener.LOG_COUNTS_RESET_INTERVAL + 1
        )

        logger.info("This is log 1")
        await empty_log_queue()
        assert caplog.text.count(expected_warning) == 0

    logger.info("This is log 2")
    logger.info("This is log 3")
    await empty_log_queue()
    assert caplog.text.count(expected_warning) == 1
    # close the handler so the queue thread stops
    logging.root.handlers[0].close()
