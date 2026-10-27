"""Broadlink test helpers."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_heartbeat():
    """Mock broadlink heartbeat."""
    with patch("homeassistant.components.broadlink.heartbeat.blk.ping"):
        yield


@pytest.fixture(autouse=True)
def mock_rediscovery(request: pytest.FixtureRequest):
    """Mock broadlink rediscovery."""
    if "no_mock_rediscovery" in request.keywords:
        yield
        return
    with patch(
        "homeassistant.components.broadlink.helpers.async_find_device_by_mac",
        return_value=None,
    ):
        yield
