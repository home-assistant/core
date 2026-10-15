"""Test the One-Time Password (OTP) init."""

from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_entry_setup_unload(
    hass: HomeAssistant, otp_config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    otp_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(otp_config_entry.entry_id)
    await hass.async_block_till_done()

    assert otp_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(otp_config_entry.entry_id)
    await hass.async_block_till_done()

    assert otp_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_update_timer_cancelled_on_unload(
    hass: HomeAssistant,
    otp_config_entry: MockConfigEntry,
    mock_pyotp: MagicMock,
) -> None:
    """Test the sensor stops updating after the entry is unloaded."""
    otp_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(otp_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(otp_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_pyotp.TOTP().now.reset_mock()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()

    mock_pyotp.TOTP().now.assert_not_called()
