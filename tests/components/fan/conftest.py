"""Fixtures for Fan platform tests."""

from collections.abc import Generator

import pytest
from pytest_homeassistant.common import mock_config_flow, mock_platform

from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, "test.config_flow")

    with mock_config_flow("test", MockFlow):
        yield
