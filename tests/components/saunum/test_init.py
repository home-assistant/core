"""Test Saunum Leil integration setup and teardown."""

from pysaunum import SaunumConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.saunum.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test integration setup and unload."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client,
) -> None:
    """Test integration setup fails when connection cannot be established."""
    mock_config_entry.add_to_hass(hass)

    mock_saunum_client.connect.side_effect = SaunumConnectionError("Connection failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_device_entry(
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device registry entry."""
    assert (
        device_entry := device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.entry_id)}
        )
    )
    assert device_entry == snapshot
