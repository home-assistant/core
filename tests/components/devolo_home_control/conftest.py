"""Fixtures for tests."""

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant

from . import configure_integration
from .mocks import DeviceMock


def pytest_configure(config):
    """Define custom markers."""
    config.addinivalue_line(
        "markers",
        "credentials_invalid: Treat credentials as invalid.",
    )
    config.addinivalue_line(
        "markers",
        "maintenance: Set maintenance mode to on.",
    )


@pytest.fixture(autouse=True)
def patch_mydevolo(request):
    """Fixture to patch mydevolo into a desired state."""
    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.credentials_valid",
        return_value=not bool(request.node.get_closest_marker("credentials_invalid")),
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.maintenance",
        return_value=bool(request.node.get_closest_marker("maintenance")),
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.get_gateway_ids",
        return_value=["1400000000000001", "1400000000000002"],
    ):
        yield


@pytest.fixture()
async def entry(hass: HomeAssistant):
    """Fixture to configure and unload the integration entry."""
    DeviceMock.available = True
    entry = configure_integration(hass)
    yield entry
    await hass.config_entries.async_unload(entry.entry_id)
