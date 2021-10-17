"""Fixtures for tests."""

from unittest.mock import patch

import pytest

from . import async_connect
from .const import DISCOVERY_INFO


@pytest.fixture()
def mock_device():
    """Mock connecting to a devolo home network device."""
    with patch("devolo_plc_api.device.Device.async_connect", async_connect), patch(
        "devolo_plc_api.device.Device.async_disconnect"
    ):
        yield


@pytest.fixture(name="info")
def mock_validate_input():
    """Mock setup entry and user input."""
    info = {
        "serial_number": DISCOVERY_INFO["properties"]["SN"],
        "title": DISCOVERY_INFO["properties"]["Product"],
    }

    with patch(
        "homeassistant.components.devolo_home_network.config_flow.validate_input",
        return_value=info,
    ):
        yield info
