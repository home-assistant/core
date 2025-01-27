"""Common fixtures for the LetPot tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from letpot.models import LetPotDevice
import pytest

from homeassistant.components.letpot.const import (
    CONF_ACCESS_TOKEN_EXPIRES,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL

from . import AUTHENTICATION

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.letpot.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock a LetPotClient."""
    with (
        patch(
            "homeassistant.components.letpot.LetPotClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.letpot.config_flow.LetPotClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login.return_value = AUTHENTICATION
        client.refresh_token.return_value = AUTHENTICATION
        client.get_devices.return_value = [
            LetPotDevice(
                serial_number="LPH21ABCD",
                name="Garden",
                device_type="LPH21",
                is_online=True,
                is_remote=False,
            )
        ]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=AUTHENTICATION.email,
        data={
            CONF_ACCESS_TOKEN: AUTHENTICATION.access_token,
            CONF_ACCESS_TOKEN_EXPIRES: AUTHENTICATION.access_token_expires,
            CONF_REFRESH_TOKEN: AUTHENTICATION.refresh_token,
            CONF_REFRESH_TOKEN_EXPIRES: AUTHENTICATION.refresh_token_expires,
            CONF_USER_ID: AUTHENTICATION.user_id,
            CONF_EMAIL: AUTHENTICATION.email,
        },
        unique_id=AUTHENTICATION.user_id,
    )
