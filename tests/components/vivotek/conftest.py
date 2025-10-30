"""Fixtures for Vivotek component tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.vivotek.const import DOMAIN
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_NAME: "Test Camera",
    CONF_IP_ADDRESS: "1.2.3.4",
    CONF_PORT: "80",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "pass1234",
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    "framerate": 2,
    "security_level": "admin",
    "stream_path": "/live.sdp",
}


@pytest.fixture
async def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch("homeassistant.components.vivotek.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock existing config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        title="Vivotek Camera",
        unique_id="test_unique_id",
    )
