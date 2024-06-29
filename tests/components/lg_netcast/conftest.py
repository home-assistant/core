"""Common fixtures and objects for the LG Netcast integration tests."""

import pytest

from homeassistant.core import HomeAssistant, ServiceCall

from tests.common import async_mock_service


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")
