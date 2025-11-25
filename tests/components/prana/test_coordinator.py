"""Tests for Prana coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.prana.const import PranaFanType, PranaSensorType
from homeassistant.components.prana.coordinator import PranaCoordinator
from homeassistant.components.prana.switch import PranaSwitchType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant  # added
from homeassistant.helpers.update_coordinator import UpdateFailed

FAKE_CONFIG_HEX = "00" * 62  # unused placeholder


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
async def test_async_update_data_parses_state_correctly(
    hass: HomeAssistant, mock_entry: ConfigEntry
) -> None:
    """Coordinator should normalize fan max_speed and convert temperatures (/10)."""
    coordinator = PranaCoordinator(hass, mock_entry, FAKE_CONFIG_HEX)

    mock_state = {
        PranaFanType.EXTRACT: {"max_speed": 100},
        PranaFanType.BOUNDED: {"max_speed": 0},
        PranaFanType.SUPPLY: {"max_speed": 0},
        PranaSwitchType.HEATER: {"state": True},
        PranaSensorType.HUMIDITY: 55,
        PranaSensorType.INSIDE_TEMPERATURE: 215,  # will be divided by 10 -> 21.5
        PranaSensorType.OUTSIDE_TEMPERATURE: 123,  # -> 12.3
    }

    # Attach a mocked api_client.get_state used by the coordinator implementation
    coordinator.api_client = MagicMock()
    coordinator.api_client.get_state = AsyncMock(return_value=mock_state)
    result = await coordinator._async_update_data()

    # Fans max_speed should be normalized (100 // 10 == 10)
    assert result[PranaFanType.EXTRACT]["max_speed"] == 10
    assert result[PranaFanType.BOUNDED]["max_speed"] == 10
    assert result[PranaFanType.SUPPLY]["max_speed"] == 10

    # Temperatures converted
    assert result[PranaSensorType.INSIDE_TEMPERATURE] == 21.5
    assert result[PranaSensorType.OUTSIDE_TEMPERATURE] == 12.3

    # Other keys remain present
    assert PranaSwitchType.HEATER in result
    assert PranaSensorType.HUMIDITY in result


@pytest.mark.asyncio
async def test_async_update_data_raises_update_failed(
    hass: HomeAssistant, mock_entry: ConfigEntry
) -> None:
    """Coordinator should raise UpdateFailed when underlying fetch fails."""
    coordinator = PranaCoordinator(hass, mock_entry, FAKE_CONFIG_HEX)

    # Mock api_client.get_state to raise
    coordinator.api_client = MagicMock()
    coordinator.api_client.get_state = AsyncMock(side_effect=Exception("boom"))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
