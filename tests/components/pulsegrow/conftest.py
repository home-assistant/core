"""Fixtures for PulseGrow integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.pulsegrow.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test User",
        data={CONF_API_KEY: "test-api-key"},
        unique_id="test-account-id",
    )


@pytest.fixture
def mock_pulsegrow_client() -> Generator[MagicMock]:
    """Return a mocked PulseGrow client."""
    with patch(
        "homeassistant.components.pulsegrow.PulsegrowClient",
        autospec=True,
    ) as mock_client_class:
        mock_client = mock_client_class.return_value

        # Mock users response
        mock_user = MagicMock()
        mock_user.user_id = "test-account-id"
        mock_user.user_name = "Test User"
        mock_user.user_email = "test@example.com"
        mock_client.get_users = AsyncMock(return_value=[mock_user])

        # Mock device with most_recent_data_point
        mock_data_point = MagicMock()
        mock_data_point.temperature_f = 72.5
        mock_data_point.humidity_rh = 55.0
        mock_data_point.vpd = 1.2
        mock_data_point.co2 = 800
        mock_data_point.light_lux = 5000
        mock_data_point.air_pressure = 101325
        mock_data_point.dp_f = 55.0
        mock_data_point.signal_strength = -50
        mock_data_point.battery_v = 3.3

        mock_device = MagicMock()
        mock_device.id = 123
        mock_device.guid = "device-123"
        mock_device.name = "Test Pulse Pro"
        mock_device.device_type = 1  # PULSE_PRO (DeviceType enum value)
        mock_device.hub_id = None
        mock_device.most_recent_data_point = mock_data_point
        mock_device.pro_light_reading_preview = None  # No pro light by default

        # Mock DeviceData response (get_all_devices returns DeviceData)
        mock_device_data = MagicMock()
        mock_device_data.devices = [mock_device]
        mock_device_data.sensors = []
        mock_client.get_all_devices = AsyncMock(return_value=mock_device_data)

        # Mock hub responses (empty by default)
        mock_client.get_hub_ids = AsyncMock(return_value=[])
        mock_client.get_hub_details = AsyncMock(return_value=None)

        yield mock_client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pulsegrow_client: MagicMock,
) -> MockConfigEntry:
    """Set up the PulseGrow integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
