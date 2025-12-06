"""Tests for Prana coordinator."""

from unittest.mock import AsyncMock, MagicMock

from prana_local_api_client.exceptions import (
    PranaApiCommunicationError,
    PranaApiUpdateFailed,
)
import pytest

from homeassistant.components.prana.coordinator import PranaCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_entry():
    """Create a fake ConfigEntry with host."""
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain="prana",
        title="Test Prana",
        data={
            "name": "Test Prana",
            "host": "127.0.0.1",
            "config": {"some_key": "some_value"},
            "mdns": "_prana._tcp.local._test",
        },
        source="user",
        entry_id="123456",
        options={},
        discovery_keys=None,
        unique_id="_prana._tcp.local._test",
        subentries_data=None,
    )


@pytest.mark.asyncio
async def test_async_update_data_returns_state(
    hass: HomeAssistant, mock_entry: ConfigEntry
) -> None:
    """Coordinator should return whatever api_client.get_state() provides."""
    coordinator = PranaCoordinator(hass, mock_entry)

    mock_state = {
        "fans": {"extract": {"max_speed": 100}},
        "sensors": {"inside_temperature": 215},
    }

    # Attach a mocked api_client.get_state used by the coordinator implementation
    coordinator.api_client = MagicMock()
    coordinator.api_client.get_state = AsyncMock(return_value=mock_state)

    result = await coordinator._async_update_data()
    assert result == mock_state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (PranaApiUpdateFailed("http error"), UpdateFailed),
        (PranaApiCommunicationError("network error"), UpdateFailed),
        (Exception("generic"), Exception),
    ],
)
async def test_async_update_data_raises_expected_exceptions(
    hass: HomeAssistant, mock_entry: ConfigEntry, exc: Exception, expected: type
) -> None:
    """Coordinator should raise UpdateFailed for known client errors and propagate others."""
    coordinator = PranaCoordinator(hass, mock_entry)

    coordinator.api_client = MagicMock()
    coordinator.api_client.get_state = AsyncMock(side_effect=exc)

    with pytest.raises(expected):
        await coordinator._async_update_data()
