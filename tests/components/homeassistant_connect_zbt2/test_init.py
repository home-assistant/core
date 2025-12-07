"""Test the Home Assistant Connect ZBT-2 integration."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant_connect_zbt2.const import DOMAIN
from homeassistant.components.usb import USBDevice
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.usb import (
    async_request_scan,
    force_usb_polling_watcher,  # noqa: F401
    patch_scanned_serial_ports,
)


async def test_setup_fails_on_missing_usb_port(hass: HomeAssistant) -> None:
    """Test setup failing when the USB port is missing."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "device": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_80B54EEFAE18-if01-port0",
            "vid": "303A",
            "pid": "4001",
            "serial_number": "80B54EEFAE18",
            "manufacturer": "Nabu Casa",
            "product": "ZBT-2",
            "firmware": "ezsp",
            "firmware_version": "7.4.4.0",
        },
        version=1,
        minor_version=1,
    )

    config_entry.add_to_hass(hass)

    # Set up the config entry
    with patch(
        "homeassistant.components.homeassistant_connect_zbt2.os.path.exists"
    ) as mock_exists:
        mock_exists.return_value = False
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Failed to set up, the device is missing
        assert config_entry.state is ConfigEntryState.SETUP_RETRY

        mock_exists.return_value = True
        async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=30))
        await hass.async_block_till_done(wait_background_tasks=True)

        # Now it's ready
        assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_usb_device_reactivity(hass: HomeAssistant) -> None:
    """Test setting up USB monitoring."""
    assert await async_setup_component(hass, "usb", {"usb": {}})

    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "device": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_80B54EEFAE18-if01-port0",
            "vid": "303A",
            "pid": "4001",
            "serial_number": "80B54EEFAE18",
            "manufacturer": "Nabu Casa",
            "product": "ZBT-2",
            "firmware": "ezsp",
            "firmware_version": "7.4.4.0",
        },
        version=1,
        minor_version=1,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_connect_zbt2.os.path.exists"
    ) as mock_exists:
        mock_exists.return_value = False
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Failed to set up, the device is missing
        assert config_entry.state is ConfigEntryState.SETUP_RETRY

        # Now we make it available but do not wait
        mock_exists.return_value = True

        with patch_scanned_serial_ports(
            return_value=[
                USBDevice(
                    device="/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_80B54EEFAE18-if01-port0",
                    vid="303A",
                    pid="4001",
                    serial_number="80B54EEFAE18",
                    manufacturer="Nabu Casa",
                    description="ZBT-2",
                )
            ],
        ):
            await async_request_scan(hass)

        # It loads immediately
        await hass.async_block_till_done(wait_background_tasks=True)
        assert config_entry.state is ConfigEntryState.LOADED

        # Wait for a bit for the USB scan debouncer to cool off
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=5))

        # Unplug the stick
        mock_exists.return_value = False

        with patch_scanned_serial_ports(return_value=[]):
            await async_request_scan(hass)

        # The integration has reloaded and is now in a failed state
        await hass.async_block_till_done(wait_background_tasks=True)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
