"""Tests for the Aprilaire integration setup."""

from unittest.mock import MagicMock, patch

from pyaprilaire.const import Attribute

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

from .conftest import MOCK_MAC, setup_integration


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test setup fails when device is not ready (missing MAC)."""

    def capture_client(host, port, callback, *args, **kwargs):
        async def on_start_listen():
            callback({Attribute.CONNECTED: True})

        mock_client.start_listen.side_effect = on_start_listen
        mock_client.wait_for_response.return_value = None
        return mock_client

    with patch(
        "homeassistant.components.aprilaire.coordinator.pyaprilaire.client.AprilaireClient",
        side_effect=capture_client,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_mac_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test setup fails with auth error when MAC doesn't match."""
    wrong_mac_data = dict(base_coordinator_data)
    wrong_mac_data[Attribute.MAC_ADDRESS] = "11:22:33:44:55:66"

    def capture_client(host, port, callback, *args, **kwargs):
        async def on_start_listen():
            callback(wrong_mac_data)

        mock_client.start_listen.side_effect = on_start_listen
        mock_client.wait_for_response.return_value = wrong_mac_data
        return mock_client

    with patch(
        "homeassistant.components.aprilaire.coordinator.pyaprilaire.client.AprilaireClient",
        side_effect=capture_client,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test unloading a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
