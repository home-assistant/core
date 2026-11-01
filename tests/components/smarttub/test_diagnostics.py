"""Test SmartTub diagnostics."""

from datetime import UTC, datetime
from unittest.mock import create_autospec

import smarttub
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    spa: smarttub.Spa,
    spa_state: smarttub.SpaStateFull,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_error = create_autospec(smarttub.SpaError, instance=True)
    mock_error.code = 11
    mock_error.title = "Flow Switch Stuck Open"
    mock_error.description = "The flow switch is stuck in the open position."
    mock_error.active = True
    mock_error.error_type = "TUB_ERROR"
    mock_error.created_at = datetime(2021, 1, 1, tzinfo=UTC)
    mock_error.updated_at = datetime(2021, 1, 2, tzinfo=UTC)
    spa.get_errors.return_value = [mock_error]

    # raw fields not otherwise parsed by the smarttub library, to verify they're redacted
    spa_state.properties["sensors"] = [
        {
            "address": "AA:BB:CC:DD:EE:FF",
            "spaId": "100672945",
            "name": "{sensor-name}",
            "type": "ibs0x",
            "subType": "magnet",
            "magnet": True,
            "pressure": None,
            "motion": None,
            "fill_drain": None,
        }
    ]
    spa_state.properties["panelSerialNumber"] = "SN0123456789"
    spa_state.properties["lastWifi"] = {
        "ssid": "MyHomeWiFi",
        "lastConnectionTimestamp": "2025-08-29T18:26:25.689257Z",
    }

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot


async def test_entry_diagnostics_no_coordinator_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    spa: smarttub.Spa,
    config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics doesn't crash when the coordinator has no data yet.

    This can happen if the initial refresh fails, e.g. because the API
    returned something the smarttub library doesn't know how to parse.
    """
    spa.get_status_full.side_effect = RuntimeError("boom")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result["spas"] == []
