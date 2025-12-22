"""Common fixtures for the Compit tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.compit.const import DOMAIN
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant

from .consts import CONFIG_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT,
        unique_id=CONFIG_INPUT[CONF_EMAIL],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.compit.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_device_data() -> dict:
    """Return mock device data."""
    # Create mock DeviceInstance objects
    mock_device_1 = MagicMock()
    mock_device_1.definition.name = "Test Device 1"

    mock_device_2 = MagicMock()
    mock_device_2.definition.name = "Test Device 2"

    return {
        1: mock_device_1,
        2: mock_device_2,
    }


@pytest.fixture
def mock_compit_api(mock_device_data: dict) -> Generator[MagicMock]:
    """Mock CompitApiConnector."""
    with (
        patch(
            "homeassistant.components.compit.config_flow.CompitApiConnector",
            autospec=True,
        ) as mock_connector_class_config,
        patch(
            "homeassistant.components.compit.CompitApiConnector",
            autospec=True,
        ) as mock_connector_class,
    ):
        # Setup the connector instance for __init__.py
        mock_connector = mock_connector_class.return_value
        mock_connector.init = AsyncMock(return_value=True)
        mock_connector.update_state = AsyncMock()
        mock_connector.all_devices = mock_device_data

        # Setup the connector instance for config_flow.py
        mock_connector_config = mock_connector_class_config.return_value
        mock_connector_config.init = AsyncMock(return_value=True)

        # Yield the config flow connector's init method for backward compatibility
        yield mock_connector_config.init


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_compit_api: AsyncMock,
) -> MockConfigEntry:
    """Set up the Compit integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
