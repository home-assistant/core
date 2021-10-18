"""Fixtures for UniFi methods."""
from __future__ import annotations

from unittest.mock import patch

from aiounifi.websocket import SIGNAL_CONNECTION_STATE, SIGNAL_DATA
import pytest


@pytest.fixture(autouse=True)
def mock_unifi_websocket():
    """No real websocket allowed."""
    with patch("aiounifi.controller.WSClient") as mock:

        def make_websocket_call(data: dict | None = None, state: str = ""):
            """Generate a websocket call."""
            if data:
                mock.return_value.data = data
                mock.call_args[1]["callback"](SIGNAL_DATA)
            elif state:
                mock.return_value.state = state
                mock.call_args[1]["callback"](SIGNAL_CONNECTION_STATE)
            else:
                raise NotImplementedError

        yield make_websocket_call


@pytest.fixture(autouse=True)
def mock_discovery():
    """No real network traffic allowed."""
    with patch(
        "homeassistant.components.unifi.config_flow.async_discover_unifi",
        return_value=None,
    ) as mock:
        yield mock
