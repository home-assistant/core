"""Tests for the iotty integration."""

from unittest.mock import MagicMock

from homeassistant.components.iotty.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry


async def test_load_unload_coordinator_called(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
    local_oauth_impl,
) -> None:
    """Test the configuration entry loading/unloading."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["auth_implementation"] is not None

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    mock_coordinator.assert_called_once()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    method_call = mock_coordinator.method_calls[0]
    name, _, _ = method_call
    assert name == "().async_config_entry_first_refresh"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_load_unload_iottyproxy_called(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iotty: MagicMock,
    local_oauth_impl,
    mock_config_entries_async_forward_entry_setup,
) -> None:
    """Test the configuration entry loading/unloading."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["auth_implementation"] is not None

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_iotty.assert_called_once()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    method_call = mock_iotty.method_calls[0]
    name, _, _ = method_call
    assert name == "().get_devices"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
