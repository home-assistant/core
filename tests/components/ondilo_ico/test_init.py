"""Test Ondilo ICO initialization."""

from typing import Any
from unittest.mock import MagicMock

from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_devices(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test devices are registered."""
    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 2

    for device_entry in device_entries:
        identifier = list(device_entry.identifiers)[0]
        assert device_entry == snapshot(name=f"{identifier[0]}-{identifier[1]}")


async def test_init_with_no_ico_attached(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    config_entry: MockConfigEntry,
    pool1: dict[str, Any],
) -> None:
    """Test if an ICO is not attached to a pool, then no sensor is created."""
    # Only one pool, but no ICO attached
    mock_ondilo_client.get_pools.return_value = pool1
    mock_ondilo_client.get_ICO_details.side_effect = None
    mock_ondilo_client.get_ICO_details.return_value = None
    await setup_integration(hass, config_entry, mock_ondilo_client)

    # No sensor should be created
    assert len(hass.states.async_all()) == 0
    # We should not have tried to retrieve pool measures
    mock_ondilo_client.get_last_pool_measures.assert_not_called()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
