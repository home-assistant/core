"""Tests for Broadlink diagnostics."""

from datetime import timedelta

import broadlink_async.exceptions as blke
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import get_device


@pytest.mark.freeze_time("2026-10-21 12:35:10+00:00")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
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

    # The clock is compared with the time it was read, not with the download.
    freezer.tick(timedelta(seconds=30))
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_setup.entry)
        == snapshot
    )


async def test_diagnostics_device_not_loaded(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test diagnostics for an entry whose device failed to set up."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.auth.side_effect = blke.NetworkTimeoutError()
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)
    assert mock_setup.entry.state is ConfigEntryState.SETUP_RETRY

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_setup.entry
    ) == {
        "entry": {
            "host": "**REDACTED**",
            "mac": "**REDACTED**",
            "type": device.devtype,
            "timeout": device.timeout,
        },
        "options": {},
    }
