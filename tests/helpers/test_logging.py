"""Test logging helpers."""

import logging

from homeassistant.helpers.logging import LOGGER_LEVELS
from homeassistant.setup import async_setup_component


async def test_set_default_log_level(hass):
    """Setting the default log level respects logger."""
    hass.helpers.logging.set_default_log_level("randomns", logging.DEBUG)
    assert logging.getLogger("randomns").isEnabledFor(logging.DEBUG) is True
    logging.getLogger("randomns").level == logging.DEBUG

    assert await async_setup_component(
        hass,
        "logger",
        {"logger": {"default": "critical", "logs": {"randomns": "info"}}},
    )
    await hass.async_block_till_done()

    assert "randomns" in hass.data[LOGGER_LEVELS]
    assert hass.data[LOGGER_LEVELS]["randomns"] == "INFO"

    assert logging.getLogger("randomns").isEnabledFor(logging.DEBUG) is False
    logging.getLogger("randomns").level == logging.INFO

    hass.helpers.logging.set_default_log_level("randomns", logging.DEBUG)
    assert logging.getLogger("randomns").isEnabledFor(logging.DEBUG) is False
    logging.getLogger("randomns").level == logging.INFO


async def test_restore_log_level(hass):
    """Setting the restore log level respects logger."""
    assert await async_setup_component(
        hass,
        "logger",
        {"logger": {"default": "critical", "logs": {"randomns": "info"}}},
    )
    await hass.async_block_till_done()

    assert "randomns" in hass.data[LOGGER_LEVELS]
    assert hass.data[LOGGER_LEVELS]["randomns"] == "INFO"

    assert logging.getLogger("randomns").isEnabledFor(logging.DEBUG) is False
    logging.getLogger("randomns").level == logging.INFO

    logging.getLogger("randomns").setLevel(logging.DEBUG)

    hass.helpers.logging.restore_log_level("randomns")
    assert logging.getLogger("randomns").isEnabledFor(logging.DEBUG) is False
    logging.getLogger("randomns").level == logging.INFO
