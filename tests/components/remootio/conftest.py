"""Common fixtures for the Remootio tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyremootio.models import DoorState
import pytest

from homeassistant.components.remootio.const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    DOMAIN,
    device_name,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.50"
MOCK_SERIAL = "2462abe6bda0nfmcfaxm"
MOCK_API_SECRET_KEY = "12" * 32
MOCK_API_AUTH_KEY = "ab" * 32

USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_API_SECRET_KEY: MOCK_API_SECRET_KEY,
    CONF_API_AUTH_KEY: MOCK_API_AUTH_KEY,
}

REAUTH_INPUT = {
    CONF_API_SECRET_KEY: "34" * 32,
    CONF_API_AUTH_KEY: "cd" * 32,
}

RECONFIGURE_HOST = "192.168.1.60"
RECONFIGURE_HOST_INPUT = {CONF_HOST: RECONFIGURE_HOST}
RECONFIGURE_KEYS_INPUT = {
    CONF_HOST: RECONFIGURE_HOST,
    **REAUTH_INPUT,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.remootio.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_remootio_client() -> Generator[AsyncMock]:
    """Mock RemootioClient for the config flow probe and runtime setup."""
    client = AsyncMock()
    client.serial_number = MOCK_SERIAL
    client.remootio_version = "remootio-3"
    client.state = DoorState.CLOSED
    client.authenticated = True
    client.listen = MagicMock(return_value=MagicMock())
    client.listen_connection = MagicMock(return_value=MagicMock())
    client.listen_auth_failure = MagicMock(return_value=MagicMock())
    client.enable_reconnect = MagicMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    with (
        patch(
            "homeassistant.components.remootio.config_flow.RemootioClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.remootio.RemootioClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for an already configured device."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data=USER_INPUT,
        title=device_name(MOCK_SERIAL),
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> MockConfigEntry:
    """Set up the Remootio integration for tests."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
