"""Provide common pytest fixtures for kraken tests."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_call_rate_limit_sleep():
    """Patch the call rate limit sleep time."""
    with patch("homeassistant.components.kraken.CALL_RATE_LIMIT_SLEEP", new=0):
        yield
