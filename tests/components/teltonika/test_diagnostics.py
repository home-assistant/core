"""Test Teltonika diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_teltasync_init", "mock_modems")
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics for the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["entry"]["data"]["password"] == "**REDACTED**"

    coordinator = result["coordinator"]
    assert coordinator["last_update_success"] is True
    assert coordinator["modems"]
    modem = coordinator["modems"][0]
    assert modem["id"] == "2-1"
    assert modem["operator"] == "test.operator"

    device = result["device"]
    assert device["manufacturer"] == "Teltonika"


@pytest.mark.usefixtures("mock_teltasync_init")
async def test_diagnostics_with_no_modems(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_modems: MagicMock,
) -> None:
    """Test diagnostics when no modems are available."""
    # Mock empty modem response
    mock_response = MagicMock()
    mock_response.data = None
    mock_modems.return_value.get_status.return_value = mock_response

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    coordinator = result["coordinator"]
    assert coordinator["modems"] == []


@pytest.mark.usefixtures("mock_teltasync_init")
async def test_diagnostics_serialization_edge_cases(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_modems: MagicMock,
) -> None:
    """Test diagnostics serialization with various data types."""

    # Create modem with edge case values
    mock_modem = MagicMock()
    mock_modem.id = "test-modem"
    mock_modem.name = "Test Modem"
    mock_modem.conntype = "LTE"
    mock_modem.operator = "Test"
    mock_modem.state = "connected"
    mock_modem.band = "B3"
    mock_modem.rssi = -75
    mock_modem.rsrp = -100
    mock_modem.rsrq = -10
    mock_modem.sinr = 10
    mock_modem.temperature = 45
    mock_modem.txbytes = 1000
    mock_modem.rxbytes = 2000

    mock_response = MagicMock()
    mock_response.data = [mock_modem]
    mock_modems.return_value.get_status.return_value = mock_response
    mock_modems.is_online.return_value = True

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    # Verify all modem attributes are serialized
    modem_data = result["coordinator"]["modems"][0]
    assert modem_data["id"] == "test-modem"
    assert modem_data["name"] == "Test Modem"
    assert modem_data["rssi"] == -75
    assert modem_data["temperature"] == 45
