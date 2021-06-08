"""Fixtures for tests."""

from unittest.mock import patch

import pytest

from . import async_connect


@pytest.fixture()
def mock_device():
    """Mock connecting to a devolo home network device."""
    with patch("devolo_plc_api.device.Device.async_connect", async_connect), patch(
        "devolo_plc_api.device.Device.async_disconnect"
    ):
        yield
