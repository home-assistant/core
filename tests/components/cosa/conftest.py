"""Common fixtures for the Cosa tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.cosa.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_ENDPOINT_DATA = {
    "id": "endpoint-123",
    "name": "Living Room Thermostat",
    "mode": "manual",
    "option": "custom",
    "currentTemperature": 21.5,
    "homeTemperature": 22,
    "awayTemperature": 18,
    "sleepTemperature": 19,
    "customTemperature": 23,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Cosa",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        unique_id="test-username",
    )


@pytest.fixture
def mock_cosa_api() -> Generator[MagicMock]:
    """Return a mocked Cosa API client."""
    with patch("homeassistant.components.cosa.CosaApi", autospec=True) as mock_api_cls:
        api = mock_api_cls.return_value
        api.async_check_connection = AsyncMock(return_value=True)
        api.async_get_endpoints = AsyncMock(return_value=[{"id": "endpoint-123"}])
        api.async_get_endpoint = AsyncMock(return_value=MOCK_ENDPOINT_DATA.copy())
        api.async_set_target_temperatures = AsyncMock(return_value=True)
        api.async_disable = AsyncMock(return_value=True)
        api.async_enable_schedule = AsyncMock(return_value=True)
        api.async_enable_custom_mode = AsyncMock(return_value=True)
        yield api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.cosa.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cosa_api: MagicMock,
) -> MockConfigEntry:
    """Set up the Cosa integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
