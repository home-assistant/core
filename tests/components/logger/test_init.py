"""The tests for the Logger component."""
from collections import namedtuple
import logging

from homeassistant.components import logger
from homeassistant.setup import async_setup_component

RECORD = namedtuple("record", ("name", "levelno"))

NO_DEFAULT_CONFIG = {"logger": {}}
NO_LOGS_CONFIG = {"logger": {"default": "info"}}
TEST_CONFIG = {
    "logger": {
        "default": "warning",
        "logs": {"test": "info", "test.child": "debug", "test.child.child": "warning"},
    }
}


async def async_setup_logger(hass, config):
    """Set up logger and save log filter."""
    await async_setup_component(hass, logger.DOMAIN, config)
    return logging.root.handlers[-1].filters[0]


async def test_logger_setup(hass):
    """Use logger to create a logging filter."""
    await async_setup_logger(hass, TEST_CONFIG)

    assert len(logging.root.handlers) > 0
    handler = logging.root.handlers[-1]

    assert len(handler.filters) == 1


async def test_logger_test_filters(hass):
    """Test resulting filter operation."""
    log_filter = await async_setup_logger(hass, TEST_CONFIG)

    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is True

    # Blocked default record
    assert not log_filter.filter(RECORD("asdf", logging.DEBUG))

    # Allowed default record
    assert log_filter.filter(RECORD("asdf", logging.WARNING))

    # Blocked named record
    assert not log_filter.filter(RECORD("test", logging.DEBUG))

    # Allowed named record
    assert log_filter.filter(RECORD("test", logging.INFO))

    # Allowed named record child
    assert log_filter.filter(RECORD("test.child", logging.INFO))

    # Allowed named record child
    assert log_filter.filter(RECORD("test.child", logging.DEBUG))

    # Blocked named record child of child
    assert not log_filter.filter(RECORD("test.child.child", logging.DEBUG))

    # Allowed named record child of child
    assert log_filter.filter(RECORD("test.child.child", logging.WARNING))


async def test_set_filter_empty_config(hass):
    """Test change log level from empty configuration."""
    log_filter = await async_setup_logger(hass, NO_LOGS_CONFIG)

    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is False

    assert not log_filter.filter(RECORD("test", logging.DEBUG))

    await hass.services.async_call(
        logger.DOMAIN, "set_default_level", {"level": "warning"}
    )
    await hass.async_block_till_done()

    assert not log_filter.filter(RECORD("test", logging.DEBUG))

    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger("").isEnabledFor(logging.WARNING) is True

    await hass.services.async_call(logger.DOMAIN, "set_level", {"test": "debug"})
    await hass.async_block_till_done()

    assert log_filter.filter(RECORD("test", logging.DEBUG))

    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is True


async def test_set_filter(hass):
    """Test change log level of existing filter."""
    log_filter = await async_setup_logger(hass, TEST_CONFIG)

    assert not log_filter.filter(RECORD("asdf", logging.DEBUG))
    assert log_filter.filter(RECORD("dummy", logging.WARNING))

    await hass.services.async_call(
        logger.DOMAIN, "set_level", {"asdf": "debug", "dummy": "info"}
    )
    await hass.async_block_till_done()

    assert log_filter.filter(RECORD("asdf", logging.DEBUG))
    assert log_filter.filter(RECORD("dummy", logging.WARNING))


async def test_set_default_filter_empty_config(hass):
    """Test change default log level from empty configuration."""
    log_filter = await async_setup_logger(hass, NO_DEFAULT_CONFIG)

    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger("").isEnabledFor(logging.WARNING) is True

    assert log_filter.filter(RECORD("test", logging.DEBUG))

    await hass.services.async_call(
        logger.DOMAIN, "set_default_level", {"level": "warning"}
    )
    await hass.async_block_till_done()

    assert not log_filter.filter(RECORD("test", logging.DEBUG))

    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger("").isEnabledFor(logging.INFO) is False
    assert logging.getLogger("").isEnabledFor(logging.WARNING) is True


async def test_set_default_filter(hass):
    """Test change default log level with existing default."""
    log_filter = await async_setup_logger(hass, TEST_CONFIG)

    assert not log_filter.filter(RECORD("asdf", logging.DEBUG))
    assert log_filter.filter(RECORD("dummy", logging.WARNING))

    await hass.services.async_call(
        logger.DOMAIN, "set_default_level", {"level": "debug"}
    )
    await hass.async_block_till_done()

    assert log_filter.filter(RECORD("asdf", logging.DEBUG))
    assert log_filter.filter(RECORD("dummy", logging.WARNING))
