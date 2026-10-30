"""Test fixtures for the Logger component."""

import logging

import pytest


@pytest.fixture(autouse=True)
def restore_logging_class():
    """Restore logging class."""
    klass = logging.getLoggerClass()
    yield
    logging.setLoggerClass(klass)


@pytest.fixture(autouse=True)
def restore_root_logger_level():
    """Restore the root logger level, which the tests change."""
    root = logging.getLogger()
    level = root.level
    yield
    root.setLevel(level)
