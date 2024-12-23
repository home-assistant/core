"""Fixtures for Homee integration tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typing_extensions import Generator

from homeassistant.components.homee.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

HOMEE_ID = "00055511EECC"
HOMEE_IP = "192.168.1.11"
TESTUSER = "testuser"
TESTPASS = "testpass"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=f"{HOMEE_ID} ({HOMEE_IP})",
        domain=DOMAIN,
        data={
            CONF_HOST: HOMEE_IP,
            CONF_USERNAME: TESTUSER,
            CONF_PASSWORD: TESTPASS,
        },
        unique_id=HOMEE_ID,
        version=1,
        minor_version=1,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.homee.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_homee() -> Generator[MagicMock]:
    """Return a mock Homee instance."""
    with patch("pyHomee.Homee", autospec=True) as mocked_homee:
        homee = mocked_homee.return_value

        homee.host = HOMEE_IP
        homee.user = TESTUSER
        homee.password = TESTPASS
        homee.settings = MagicMock()
        homee.settings.uid = HOMEE_ID
        homee.reconnect_interval = 10

        homee.get_access_token.return_value = "test_token"
        homee.wait_until_connected.return_value = True
        homee.wait_until_disconnected.return_value = True

        yield homee
