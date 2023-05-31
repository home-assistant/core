"""Test fixtures for the Logger component."""
import logging

import pytest


@pytest.fixture(autouse=True)
def restore_logging_class():
    """Restore logging class."""
    klass = logging.getLoggerClass()
    yield
    logging.setLoggerClass(klass)
