"""Test jsonlog component."""
from __future__ import annotations

import json
import logging
from pathlib import Path
import random

import pytest

from homeassistant.components import jsonlog
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

_LOGGER = logging.getLogger("test_logger")


@pytest.fixture
def logfile(tmp_path: Path) -> Path:
    """Generate a random logfile path."""
    subdir = tmp_path / str(random.randint(0, 1000))
    subdir.mkdir()
    return subdir / "test.log"


@pytest.fixture
def basic_config(logfile: Path) -> dict:
    """Generate a basic config for jsonlog."""
    return {
        jsonlog.DOMAIN: {
            jsonlog.CONF_FILENAME: str(logfile),
        }
    }


def _generate_and_log_exception(exception, log):
    try:
        raise Exception(exception)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception(log)


def find_log_record(logfile: Path, level: str) -> dict:
    """Return log with specific level."""
    with logfile.open() as logobj:
        logs = logobj.readlines()
    logs.reverse()
    for line in logs:
        try:
            log_record = json.loads(line)
        except Exception as exc:
            raise AssertionError("Could not parse JSON\n%s", logs) from exc
        if "levelname" in log_record and log_record["levelname"] == level:
            return log_record
    raise AssertionError("No matching log record found %s", logs)


def assert_log(log, exception, message, level, logger="test_logger"):
    """Assert that specified values are in a specific log entry."""
    assert log["name"] == logger
    assert exception in log.get("exc_info", "")
    assert message == log["message"]
    assert level == log["levelname"]


async def test_exception(
    hass: HomeAssistant, basic_config: dict, logfile: Path
) -> None:
    """Test that exceptions are logged and retrieved correctly."""
    await async_setup_component(hass, jsonlog.DOMAIN, basic_config)

    _generate_and_log_exception("exception message", "log message")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    log = find_log_record(logfile, "ERROR")
    assert_log(log, "exception message", "log message", "ERROR")


async def test_warning(hass: HomeAssistant, basic_config: dict, logfile: Path) -> None:
    """Test that warning are logged and retrieved correctly."""
    await async_setup_component(hass, jsonlog.DOMAIN, basic_config)

    _LOGGER.warning("warning message")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    log = find_log_record(logfile, "WARNING")
    assert_log(log, "", "warning message", "WARNING")


async def test_warning_good_format(
    hass: HomeAssistant, basic_config: dict, logfile: Path
) -> None:
    """Test that warning with good format arguments are logged and retrieved correctly."""
    await async_setup_component(hass, jsonlog.DOMAIN, basic_config)

    _LOGGER.warning("warning message: %s", "test")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    log = find_log_record(logfile, "WARNING")
    assert_log(log, "", "warning message: test", "WARNING")


async def test_warning_missing_format_args(
    hass: HomeAssistant, basic_config: dict, logfile: Path
) -> None:
    """Test that warning with missing format arguments are logged and retrieved correctly."""
    await async_setup_component(hass, jsonlog.DOMAIN, basic_config)

    _LOGGER.warning("warning message missing a format arg %s")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    log = find_log_record(logfile, "WARNING")
    assert_log(log, "", "warning message missing a format arg %s", "WARNING")


async def test_error(hass: HomeAssistant, basic_config: dict, logfile: Path) -> None:
    """Test that errors are logged and retrieved correctly."""
    await async_setup_component(hass, jsonlog.DOMAIN, basic_config)

    _LOGGER.error("error message")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    log = find_log_record(logfile, "ERROR")
    assert_log(log, "", "error message", "ERROR")


async def test_critical(hass: HomeAssistant, basic_config: dict, logfile: Path) -> None:
    """Test that critical are logged and retrieved correctly."""
    await async_setup_component(hass, jsonlog.DOMAIN, basic_config)

    _LOGGER.critical("critical message")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    log = find_log_record(logfile, "CRITICAL")
    assert_log(log, "", "critical message", "CRITICAL")


async def test_service_rotate_logfile(
    hass: HomeAssistant, basic_config: dict, logfile: Path
) -> None:
    """Test that the log can be rotated via a service call."""

    await async_setup_component(hass, jsonlog.DOMAIN, basic_config)
    assert logfile.exists()
    assert not logfile.with_suffix(".log.1").exists()

    _LOGGER.error("error message")

    await hass.services.async_call(jsonlog.DOMAIN, jsonlog.SERVICE_ROTATE)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    with pytest.raises(AssertionError):
        find_log_record(logfile, "ERROR")
    log = find_log_record(logfile, "INFO")
    assert_log(log, "", "Rotated log file", "INFO", logger=jsonlog.__package__)
    assert logfile.exists()
    assert logfile.with_suffix(".log.1").exists()
