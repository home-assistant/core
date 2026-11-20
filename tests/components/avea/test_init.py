"""Tests for the Avea integration setup."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant


async def test_setup_entry_retries_when_ble_device_is_missing(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the Bluetooth device is unavailable."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.avea.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.avea.async_address_reachability_diagnostics",
            return_value="mock reachability reason",
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        "Could not find Avea device with address "
        f"{mock_config_entry.data[CONF_ADDRESS]}: mock reachability reason"
        in caplog.text
    )
