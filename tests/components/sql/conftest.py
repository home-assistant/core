"""Fixtures for the SQL integration."""

from __future__ import annotations

from collections.abc import Generator
import logging
from unittest.mock import AsyncMock, patch

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Configure pytest."""
    logger = logging.getLogger("sqlalchemy.engine")
    logger.setLevel(logging.CRITICAL)
    logger2 = logging.getLogger("homeassistant.components.recorder")
    logger2.setLevel(logging.CRITICAL)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sql.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
