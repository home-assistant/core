"""Fixtures for PulseGrow integration tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

from aiopulsegrow import Device, DeviceData, UserUsage
import pytest

from homeassistant.components.pulsegrow.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


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

        # Mock users response using JSON fixture
        users_data = load_fixture("users.json", DOMAIN)
        users_json = json.loads(users_data)
        mock_client.get_users = AsyncMock(
            return_value=[UserUsage.from_dict(u) for u in users_json]
        )

        # Mock device using JSON fixture
        device_data = load_fixture("device.json", DOMAIN)
        device_json = json.loads(device_data)
        device = Device.from_dict(device_json)

        # Mock DeviceData response (get_all_devices returns DeviceData)
        mock_device_data = MagicMock(spec=DeviceData)
        mock_device_data.devices = [device]
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
