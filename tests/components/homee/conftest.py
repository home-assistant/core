"""Fixtures for Homee integration tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typing_extensions import Generator
import voluptuous as vol

from homeassistant.components.homee.const import (
    CONF_ADD_HOMEE_DATA,
    CONF_DOOR_GROUPS,
    CONF_WINDOW_GROUPS,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from tests.common import MockConfigEntry

HOMEE_ID = "00055511EECC"
HOMEE_IP = "192.168.1.11"
TESTUSER = "testuser"
TESTPASS = "testpass"

GROUPS_SELECTION = {"1": "Group1 (0)", "3": "Group2 (0)"}

SCHEMA_IMPORT_ALL = vol.Schema(
    {
        vol.Required(
            CONF_WINDOW_GROUPS,
            default=[],
        ): cv.multi_select(GROUPS_SELECTION),
        vol.Required(
            CONF_DOOR_GROUPS,
            default=[],
        ): cv.multi_select(GROUPS_SELECTION),
    }
)


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
        options={CONF_ADD_HOMEE_DATA: False},
        unique_id=HOMEE_ID,
        version=3,
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
    with patch(
        "homeassistant.components.homee.config_flow.validate_and_connect", autospec=True
    ) as mocked_homee:
        homee = mocked_homee.return_value

        homee.host = HOMEE_IP
        homee.user = TESTUSER
        homee.password = TESTPASS
        homee.settings.uid = HOMEE_ID
        homee.reconnect_interval = 10

        homee.get_access_token.return_value = "test_token"
        homee.wait_until_connected.return_value = True
        homee.wait_until_disconnected.return_value = True

        yield homee
