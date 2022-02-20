"""Pytest module configuration."""
from unittest.mock import patch

import pytest

from .common import FakeDiscovery, build_device_mock


@pytest.fixture(autouse=True, name="discovery")
def discovery_fixture():
    """Patch the discovery object."""
    with patch("homeassistant.components.gree.bridge.Discovery") as mock:
        mock.return_value = FakeDiscovery()
        yield mock


@pytest.fixture(autouse=True, name="device")
def device_fixture():
    """Patch the device search and bind."""
    with patch(
        "homeassistant.components.gree.bridge.Device",
        return_value=build_device_mock(),
    ) as mock:
        yield mock
