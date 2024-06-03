"""Tests for the One-Time Password (OTP) Sensors."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    otp_config_entry: MockConfigEntry,
    mock_pyotp: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of ista EcoTrend sensor platform."""

    otp_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(otp_config_entry.entry_id)
    await hass.async_block_till_done()

    assert otp_config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.otp_sensor") == snapshot
