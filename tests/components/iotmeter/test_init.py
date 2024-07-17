"""Test module for IoTMeter integration setup in Home Assistant."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.iotmeter import async_setup_entry, async_unload_entry
from homeassistant.components.iotmeter.const import DOMAIN
from homeassistant.components.iotmeter.coordinator import IotMeterDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the IoTMeter integration from a config entry."""
    mock_coordinator = AsyncMock(spec=IotMeterDataUpdateCoordinator)
    mock_coordinator.async_config_entry_first_refresh = AsyncMock(return_value=None)

    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="IoTMeter",
        data={"ip_address": "192.168.1.1", "port": 8000},
        source="test",
        options={},
        entry_id="1",
        unique_id="unique_id_123",
    )

    with (
        patch(
            "homeassistant.components.iotmeter.IotMeterDataUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=None,
        ),
    ):
        await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

        assert DOMAIN in hass.data
        assert hass.data[DOMAIN]["coordinator"] == mock_coordinator
        assert hass.data[DOMAIN]["ip_address"] == "192.168.1.1"
        assert hass.data[DOMAIN]["port"] == 8000

        mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the IoTMeter integration."""
    mock_coordinator = AsyncMock(spec=IotMeterDataUpdateCoordinator)

    hass.data[DOMAIN] = {
        "coordinator": mock_coordinator,
        "ip_address": "192.168.1.1",
        "port": 8000,
    }

    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="IoTMeter",
        data={"ip_address": "192.168.1.1", "port": 8000},
        source="test",
        options={},
        entry_id="1",
        unique_id="unique_id_123",
    )

    with (
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ),
    ):
        await async_unload_entry(hass, config_entry)
        await hass.async_block_till_done()

        assert DOMAIN not in hass.data
