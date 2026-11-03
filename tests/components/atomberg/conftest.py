"""Atomberg tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_array_fixture

from homeassistant.components.atomberg.api import AtombergDevice
from homeassistant.components.atomberg.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.const import CONF_API_KEY

API_KEY = "test-api-key"
REFRESH_TOKEN = "test-refresh-token"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.atomberg.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Atomberg",
        data={CONF_API_KEY: API_KEY, CONF_REFRESH_TOKEN: REFRESH_TOKEN},
        unique_id=API_KEY,
    )


@pytest.fixture
def mock_client_class() -> Generator[MagicMock]:
    """Mock the client class."""
    with (
        patch(
            "homeassistant.components.atomberg.AtombergClient", autospec=True
        ) as mock_class,
        patch(
            "homeassistant.components.atomberg.config_flow.AtombergClient",
            new=mock_class,
        ),
    ):
        yield mock_class


@pytest.fixture
def mock_client(mock_client_class: MagicMock) -> AsyncMock:
    """Mock a client returning two fans, a water purifier and a lock."""
    client = mock_client_class.return_value
    client.async_get_devices.return_value = [
        AtombergDevice.from_api(device)
        for device in load_json_array_fixture("devices.json", DOMAIN)
    ]
    client.async_get_states.return_value = {
        state["device_id"]: state
        for state in load_json_array_fixture("states.json", DOMAIN)
    }
    client.async_get_guest_pin.return_value = {
        "otp": "482915",
        "validStartTime": 1793700000,
        "validEndTime": 1793714400,
    }
    return client
