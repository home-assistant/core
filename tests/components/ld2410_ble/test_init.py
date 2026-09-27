"""Test the LD2410 BLE integration init."""

from unittest.mock import patch

import pytest

from homeassistant.components.ld2410_ble.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import LD2410_BLE_DISCOVERY_INFO

from tests.common import MockConfigEntry


async def test_setup_retries_when_device_not_found(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup is retried with a diagnostic reason when the device is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=LD2410_BLE_DISCOVERY_INFO.address,
        data={CONF_ADDRESS: LD2410_BLE_DISCOVERY_INFO.address},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.ld2410_ble.get_device",
            return_value=None,
        ),
        patch(
            "homeassistant.components.ld2410_ble.bluetooth."
            "async_address_reachability_diagnostics",
            return_value="mock reachability reason",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        "Could not find LD2410B device with address "
        f"{LD2410_BLE_DISCOVERY_INFO.address}: mock reachability reason" in caplog.text
    )
