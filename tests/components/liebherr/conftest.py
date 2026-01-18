"""Common fixtures for the liebherr tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyliebherrhomeapi import Device, DeviceType
import pytest

from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.liebherr.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        unique_id="test-api-key",
        title="Mock Title",
    )


@pytest.fixture
def mock_liebherr_client() -> Generator[MagicMock]:
    """Return a mocked Liebherr client."""
    with patch(
        "homeassistant.components.liebherr.LiebherrClient", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.get_devices.return_value = [
            Device(
                device_id="test_device_id",
                nickname="Test Device",
                device_type=DeviceType.FRIDGE,
            )
        ]
        # Default empty device state - tests can override
        client.get_device_state.return_value = None
        client.set_temperature = AsyncMock()
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Liebherr integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
