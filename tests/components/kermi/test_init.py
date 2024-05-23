"""Init tests for the Kermi component."""

from unittest.mock import patch

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException
import pytest

from homeassistant.components.kermi import async_setup_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


async def test_async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test a successful setup entry."""
    with (
        patch.object(AsyncModbusTcpClient, "connect", return_value=True),
        patch("homeassistant.components.kermi.async_update_data", return_value=True),
    ):
        assert await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()


async def test_async_setup_entry_failure(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test setup entry fails if connection fails."""
    with (
        patch.object(AsyncModbusTcpClient, "connect", side_effect=ConnectionException),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, config_entry)


async def test_async_update_data(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test the async_update_data function."""
    with (
        patch.object(AsyncModbusTcpClient, "connect", return_value=True),
        patch("homeassistant.components.kermi.async_update_data", return_value=True),
    ):
        assert await async_setup_entry(hass, config_entry)
        coordinator = hass.data["kermi"][config_entry.entry_id]["coordinator"]
        assert coordinator.data is not None
