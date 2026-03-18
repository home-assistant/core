"""Fixtures for water heater platform tests."""

from collections.abc import Generator

import pytest

from homeassistant.config_entries import ConfigFlow
from homeassistant.core import HomeAssistant

from tests.common import mock_config_flow, mock_platform


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, "test.config_flow")

    with mock_config_flow("test", MockFlow):
        yield
