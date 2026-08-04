"""Tests for the Theben Conexa coordinator."""

from types import SimpleNamespace

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_entry_initializes_coordinator(
    hass: HomeAssistant,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup initializes runtime coordinator data and schedules updates."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator._api is mock_conexa_smgw.client
    assert coordinator.gateway_info is mock_conexa_smgw.client.gatewayInfo
    assert coordinator._scheduled_updates is not None


async def test_setup_entry_not_ready_when_gateway_unreachable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_conexa_smgw: SimpleNamespace,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when gateway is unreachable and no entities are created."""
    mock_config_entry.add_to_hass(hass)

    mock_conexa_smgw.network.side_effect = TimeoutError
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
