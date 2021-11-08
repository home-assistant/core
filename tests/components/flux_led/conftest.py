"""Tests for the flux_led integration."""

import pytest

from tests.common import mock_device_registry


@pytest.fixture(name="device_reg")
def device_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)
