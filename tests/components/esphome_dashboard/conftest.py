"""Common fixtures for the ESPHome Dashboard tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.esphome_dashboard.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="ESPHome Dashboard (192.168.1.100:6052)",
        domain=DOMAIN,
        data={CONF_URL: "http://192.168.1.100:6052"},
        unique_id="http://192.168.1.100:6052",
    )


@pytest.fixture
def mock_dashboard_api() -> Generator[MagicMock]:
    """Return a mocked ESPHome Dashboard API."""
    api = MagicMock()
    api.request = AsyncMock(return_value=None)
    api.get_devices = AsyncMock(
        return_value={
            "configured": [
                {
                    "name": "test_device",
                    "deployed_version": "2023.12.0",
                    "current_version": "2024.1.0",
                    "configuration": "test_device.yaml",
                },
                {
                    "name": "test_device_2",
                    "deployed_version": "2023.11.0",
                    "current_version": "2023.11.0",
                    "configuration": "test_device_2.yaml",
                },
            ]
        }
    )
    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=api,
    ):
        yield api


@pytest.fixture
def mock_dashboard_api_no_devices() -> Generator[MagicMock]:
    """Return a mocked ESPHome Dashboard API with no devices."""
    api = MagicMock()
    api.request = AsyncMock(return_value=None)
    api.get_devices = AsyncMock(return_value={"configured": []})
    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=api,
    ):
        yield api


@pytest.fixture
def mock_dashboard_api_error() -> Generator[MagicMock]:
    """Return a mocked ESPHome Dashboard API that raises an error."""
    api = MagicMock()
    api.request = AsyncMock(return_value=None)
    api.get_devices = AsyncMock(side_effect=Exception("Connection error"))
    with patch(
        "homeassistant.components.esphome_dashboard.ESPHomeDashboardAPI",
        return_value=api,
    ):
        yield api


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dashboard_api: MagicMock,
) -> MockConfigEntry:
    """Set up the ESPHome Dashboard integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
