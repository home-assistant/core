"""Broadlink test helpers."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_heartbeat():
    """Mock broadlink heartbeat."""
    with patch("homeassistant.components.broadlink.heartbeat.blk.ping"):
        yield
