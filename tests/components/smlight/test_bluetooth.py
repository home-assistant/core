"""Tests for the SMLIGHT Bluetooth platform."""

from unittest.mock import ANY, MagicMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_ultima_client")
async def test_bluetooth_scanner_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_scanner: MagicMock,
    mock_bluetooth_scanner: MagicMock,
) -> None:
    """Test setting up and unloading SMLIGHT Bluetooth scanner (lifecycle)."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_connect_scanner.assert_called_once_with(
        source=mock_config_entry.unique_id,
        name=mock_config_entry.title,
        host=mock_config_entry.data[CONF_HOST],
        port=5050,
    )

    client_data = mock_connect_scanner.return_value
    client_data.client.start.assert_called_once()
    mock_bluetooth_scanner.assert_called_once_with(
        hass,
        client_data.scanner,
        source_domain="smlight",
        source_model="SLZB-Ultima3",
        source_config_entry_id=mock_config_entry.entry_id,
        source_device_id=ANY,
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    client_data.client.stop.assert_called_once()


@pytest.mark.usefixtures("mock_smlight_client")
async def test_bluetooth_not_started_for_classic_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_scanner: MagicMock,
) -> None:
    """Test that bluetooth scanner is not started for classic (non-U) devices."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_connect_scanner.assert_not_called()
