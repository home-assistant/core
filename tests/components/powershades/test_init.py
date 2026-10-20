"""Tests for setting up and unloading the PowerShades integration."""

from unittest.mock import MagicMock

from pyowershades import PowerShadesTimeoutError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.powershades.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import TEST_IP, TEST_SERIAL


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The entry retries setup if the device doesn't respond."""
    mock_powershades_connection.async_request.side_effect = PowerShadesTimeoutError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_powershades_connection.close.assert_called_once()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unloading the entry closes the connection."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_powershades_connection.close.assert_called_once()


async def test_device_without_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A shade without a known name is named after its IP address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**mock_config_entry.data, "name": None},
        unique_id=mock_config_entry.unique_id,
    )
    await setup_integration(hass, entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(TEST_SERIAL)), entry.entry_id
    )
    assert device.name == f"PowerShade {TEST_IP}"
