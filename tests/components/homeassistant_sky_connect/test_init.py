"""Test the Home Assistant SkyConnect integration."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
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


async def test_config_entry_migration_v2(hass: HomeAssistant) -> None:
    """Test migrating config entries from v1 to v2 format."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "device": "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
            "vid": "10C4",
            "pid": "EA60",
            "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
            "manufacturer": "Nabu Casa",
            "description": "SkyConnect v1.0",
        },
        version=1,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_sky_connect.guess_firmware_info",
        return_value=FirmwareInfo(
            device="/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
            firmware_version=None,
            firmware_type=ApplicationType.SPINEL,
            source="otbr",
            owners=[],
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 1
    assert config_entry.minor_version == 3
    assert config_entry.data == {
        "description": "SkyConnect v1.0",
        "device": "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
        "vid": "10C4",
        "pid": "EA60",
        "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
        "manufacturer": "Nabu Casa",
        "product": "SkyConnect v1.0",  # `description` has been copied to `product`
        "firmware": "spinel",  # new key
        "firmware_version": None,  # new key
    }

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_setup_fails_on_missing_usb_port(hass: HomeAssistant) -> None:
    """Test setup failing when the USB port is missing."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "description": "SkyConnect v1.0",
            "device": "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
            "vid": "10C4",
            "pid": "EA60",
            "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
            "manufacturer": "Nabu Casa",
            "product": "SkyConnect v1.0",
            "firmware": "ezsp",
            "firmware_version": "7.4.4.0",
        },
        version=1,
        minor_version=3,
    )

    config_entry.add_to_hass(hass)

    # Set up the config entry
    with patch(
        "homeassistant.components.homeassistant_sky_connect.os.path.exists"
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
            "description": "SkyConnect v1.0",
            "device": "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
            "vid": "10C4",
            "pid": "EA60",
            "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
            "manufacturer": "Nabu Casa",
            "product": "SkyConnect v1.0",
            "firmware": "ezsp",
            "firmware_version": "7.4.4.0",
        },
        version=1,
        minor_version=3,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_sky_connect.os.path.exists"
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
                    device="/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
                    vid="10C4",
                    pid="EA60",
                    serial_number="3c0ed67c628beb11b1cd64a0f320645d",
                    manufacturer="Nabu Casa",
                    description="SkyConnect v1.0",
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
