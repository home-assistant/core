"""Test Snooz configuration."""

from unittest.mock import patch

import pytest

from homeassistant.components.snooz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import TEST_ADDRESS, TEST_PAIRING_TOKEN, SnoozFixture

from tests.common import MockConfigEntry


async def test_setup_retries_when_device_not_found(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup is retried with a diagnostic reason when the device is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_TOKEN: TEST_PAIRING_TOKEN},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snooz.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.snooz.async_address_reachability_diagnostics",
            return_value="mock reachability reason",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        f"Could not find Snooz with address {TEST_ADDRESS}: mock reachability reason"
        in caplog.text
    )


async def test_removing_entry_cleans_up_connections(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture
) -> None:
    """Tests setup and removal of a config entry, cleaning up connections."""
    await hass.config_entries.async_remove(mock_connected_snooz.entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_connected_snooz.device.is_connected


async def test_reloading_entry_cleans_up_connections(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture
) -> None:
    """Test reloading an entry disconnects any existing connections."""
    await hass.config_entries.async_reload(mock_connected_snooz.entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_connected_snooz.device.is_connected
