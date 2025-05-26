"""Fixtures for Homee integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.homee.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

HOMEE_ID = "00055511EECC"
HOMEE_IP = "192.168.1.11"
HOMEE_NAME = "TestHomee"
TESTUSER = "testuser"
TESTPASS = "testpass"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.homee.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=f"{HOMEE_NAME} ({HOMEE_IP})",
        domain=DOMAIN,
        data={
            CONF_HOST: HOMEE_IP,
            CONF_USERNAME: TESTUSER,
            CONF_PASSWORD: TESTPASS,
        },
        unique_id=HOMEE_ID,
    )


@pytest.fixture
def mock_homee() -> Generator[AsyncMock]:
    """Return a mock Homee instance."""
    with (
        patch(
            "homeassistant.components.homee.config_flow.Homee", autospec=True
        ) as mocked_homee,
        patch(
            "homeassistant.components.homee.Homee",
            new=mocked_homee,
        ),
    ):
        homee = mocked_homee.return_value

        homee.host = HOMEE_IP
        homee.user = TESTUSER
        homee.password = TESTPASS
        homee.settings = MagicMock()
        homee.settings.uid = HOMEE_ID
        homee.settings.homee_name = HOMEE_NAME
        homee.settings.version = "1.2.3"
        homee.settings.mac_address = "00:05:55:11:ee:cc"
        homee.reconnect_interval = 10
        homee.connected = True

        homee.get_access_token.return_value = "test_token"

        yield homee
