"""Fixtures for tests."""
from itertools import cycle
from unittest.mock import patch

import pytest

from .const import DISCOVERY_INFO, IP
from .mock import MockDevice


@pytest.fixture
def mock_device():
    """Mock connecting to a devolo home network device."""
    device = MockDevice(ip=IP)
    with patch(
        "homeassistant.components.devolo_home_network.Device",
        side_effect=cycle([device]),
    ):
        yield device


@pytest.fixture(name="info")
def mock_validate_input():
    """Mock setup entry and user input."""
    info = {
        "serial_number": DISCOVERY_INFO.properties["SN"],
        "title": DISCOVERY_INFO.properties["Product"],
    }

    with patch(
        "homeassistant.components.devolo_home_network.config_flow.validate_input",
        return_value=info,
    ):
        yield info


@pytest.fixture(autouse=True)
def devolo_home_network_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""
