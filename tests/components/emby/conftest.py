"""Fixtures for the emby tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.emby.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant

from .const import TEST_HOST_VALUE, TEST_API_KEY_VALUE, TEST_PORT_VALUE, TEST_SSL_VALUE

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry():
    """Prevent setup of integration during tests."""
    with patch(
        "homeassistant.components.emby.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock the config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: TEST_API_KEY_VALUE,
            CONF_HOST: TEST_HOST_VALUE,
            CONF_PORT: TEST_PORT_VALUE,
            CONF_SSL: TEST_SSL_VALUE,
        },
        title=f"{TEST_HOST_VALUE}:{TEST_PORT_VALUE}",
        unique_id=f"{TEST_HOST_VALUE}:{TEST_PORT_VALUE}",
    )
