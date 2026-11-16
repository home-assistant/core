"""Tests for the Broadlink diagnostics."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import get_device


@pytest.mark.freeze_time("2026-10-21 12:35:10+00:00")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test config entry diagnostics."""
    await hass.config.async_set_time_zone("UTC")
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.get_full_status.return_value = {
        "sensor": 0,
        "power": 1,
        "auto_mode": 0,
        "active": 1,
        "room_temp": 22,
        "thermostat_temp": 23,
        "external_temp": 30,
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
