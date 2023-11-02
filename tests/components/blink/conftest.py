"""Fixtures for the Blink integration tests."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from homeassistant.components.blink.const import CONF_DEVICE_ID, DEVICE_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture(name="blink_api")
def blink_api_fixture() -> MagicMock:
    """Set up Blink API fixture."""
    with patch("homeassistant.components.blink.Blink", autospec=True) as mock_blink_api:
        mock_blink_api.available = True
        mock_blink_api.start = AsyncMock(return_value=True)
        mock_blink_api.refresh = AsyncMock(return_value=True)
        mock_blink_api.sync = MagicMock(return_value=True)
        mock_blink_api.cameras = MagicMock(return_value=True)
        yield mock_blink_api


@pytest.fixture(name="blink_auth_api")
def blink_auth_api_fixture():
    """Set up Blink API fixture."""
    with patch(
        "homeassistant.components.blink.Auth", autospec=True
    ) as mock_blink_auth_api:
        mock_blink_auth_api.check_key_required.return_value = False
        mock_blink_auth_api.send_auth_key = AsyncMock(return_value=True)
        yield mock_blink_auth_api


@pytest.fixture(name="mock_config_entry")
def mock_config_fixture():
    """Return a fake config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "Password",
            CONF_DEVICE_ID: DEVICE_ID,
        },
        entry_id=str(uuid4()),
        version=3,
    )
