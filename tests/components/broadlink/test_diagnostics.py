"""Tests for Broadlink diagnostics."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import get_device

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2026-10-21 12:35:10+00:00")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a Hysen thermostat."""
    await hass.config.async_set_time_zone("UTC")
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.get_full_status.return_value = {
        "power": 1,
        "auto_mode": 0,
        "loop_mode": 1,
        "sensor": 0,
        "room_temp": 21.5,
        "thermostat_temp": 22.0,
        "svh": 35,
        "svl": 5,
        "hour": 12,
        "min": 34,
        "sec": 56,
        "dayofweek": 3,
    }
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_setup.entry)
        == snapshot
    )
