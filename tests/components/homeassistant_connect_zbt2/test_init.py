"""Test the Home Assistant Connect ZBT-2 integration."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant_connect_zbt2.const import DOMAIN
from homeassistant.components.usb import DOMAIN as USB_DOMAIN, USBDevice
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.usb import async_request_scan, patch_scanned_serial_ports
from tests.components.usb.conftest import force_usb_polling_watcher  # noqa: F401


async def test_config_entry_migration_v2(hass: HomeAssistant) -> None:
    """Test migrating config entries from v1.1 to v1.2 for serial unique ID."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="303A:4001_80B54EEFAE18_Nabu Casa_ZBT-2",
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
        "homeassistant.components.homeassistant_connect_zbt2.os.path.exists",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.version == 1
    assert config_entry.minor_version == 2
    assert config_entry.unique_id == "80B54EEFAE18"


@pytest.mark.parametrize(
    ("older", "newer", "serial_number"),
    [
        # Same physical adapter, different unique IDs because the `product` field
        # differed between HA versions that built the ID from `port.product` vs
        # `port.description`
        (
            {
                "unique_id": "303A:831A_DCB4D90BBCE4_Nabu Casa_ZBT-2 - Nabu Casa ZBT-2",
                "source": "usb",
                "data": {
                    "device": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_DCB4D90BBCE4-if00",
                    "firmware": "ezsp",
                    "firmware_version": "7.5.1.0 build 0 (20260224005837)",
                    "manufacturer": "Nabu Casa",
                    "pid": "831A",
                    "product": "ZBT-2 - Nabu Casa ZBT-2",
                    "serial_number": "DCB4D90BBCE4",
                    "vid": "303A",
                },
            },
            {
                "unique_id": "303A:831A_DCB4D90BBCE4_Nabu Casa_ZBT-2",
                "source": "import",
                "data": {
                    "device": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_DCB4D90BBCE4-if00",
                    "firmware": "ezsp",
                    "firmware_version": "7.5.1.0 build 0 (20260224005837)",
                    "manufacturer": "Nabu Casa",
                    "pid": "831A",
                    "product": "ZBT-2",
                    "serial_number": "DCB4D90BBCE4",
                    "vid": "303A",
                },
            },
            "DCB4D90BBCE4",
        ),
        # Two entries with identical unique IDs for the same adapter
        (
            {
                "unique_id": "303A:831A_DCB4D910DBB4_Nabu_Casa_ZBT-2",
                "source": "usb",
                "data": {
                    "device": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_DCB4D910DBB4-if00",
                    "firmware": "ezsp",
                    "firmware_version": "7.5.1.0 build 0 (20260224005837)",
                    "manufacturer": "Nabu Casa",
                    "pid": "831A",
                    "product": "ZBT-2",
                    "serial_number": "DCB4D910DBB4",
                    "vid": "303A",
                },
            },
            {
                "unique_id": "303A:831A_DCB4D910DBB4_Nabu_Casa_ZBT-2",
                "source": "import",
                "data": {
                    "device": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_DCB4D910DBB4-if00",
                    "firmware": "spinel",
                    "firmware_version": (
                        "SL-OPENTHREAD/2.7.2.0_GitHub-fb0446f53;"
                        " EFR32; Jan 11 2026 17:52:09"
                    ),
                    "manufacturer": "Nabu Casa",
                    "pid": "831A",
                    "product": "ZBT-2",
                    "serial_number": "DCB4D910DBB4",
                    "vid": "303A",
                },
            },
            "DCB4D910DBB4",
        ),
    ],
)
async def test_config_entry_migration_v2_collapses_duplicates(
    hass: HomeAssistant,
    older: dict,
    newer: dict,
    serial_number: str,
) -> None:
    """Test that v1.2 migration removes duplicate entries sharing a serial number."""

    older_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=older["unique_id"],
        source=older["source"],
        data=older["data"],
        version=1,
        minor_version=1,
    )
    older_entry.add_to_hass(hass)

    newer_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=newer["unique_id"],
        source=newer["source"],
        data=newer["data"],
        version=1,
        minor_version=1,
    )
    newer_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_connect_zbt2.os.path.exists",
        return_value=True,
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    remaining_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(remaining_entries) == 1
    unique_entry = remaining_entries[0]
    assert unique_entry.entry_id == newer_entry.entry_id
    assert unique_entry.minor_version == 2
    assert unique_entry.unique_id == serial_number
    assert unique_entry.data == newer["data"]
    assert hass.config_entries.async_get_entry(older_entry.entry_id) is None


@pytest.mark.parametrize(
    ("sibling_source", "sibling_disabled_by"),
    [
        (SOURCE_IGNORE, None),
        ("usb", ConfigEntryDisabler.USER),
    ],
)
async def test_config_entry_migration_v2_prefers_active_entry(
    hass: HomeAssistant,
    sibling_source: str,
    sibling_disabled_by: ConfigEntryDisabler | None,
) -> None:
    """Test v1.2 migration prefers an active entry over ignored/disabled siblings."""
    serial_number = "80B54EEFAE18"
    active_data = {
        "device": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_80B54EEFAE18-if01-port0",
        "vid": "303A",
        "pid": "4001",
        "serial_number": serial_number,
        "manufacturer": "Nabu Casa",
        "product": "ZBT-2",
        "firmware": "ezsp",
        "firmware_version": "7.4.4.0",
    }

    active_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="303A:4001_80B54EEFAE18_Nabu Casa_ZBT-2",
        source="usb",
        data=active_data,
        version=1,
        minor_version=1,
    )
    active_entry.add_to_hass(hass)

    sibling_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=serial_number,
        source=sibling_source,
        disabled_by=sibling_disabled_by,
        data=dict(active_data),
        version=1,
        minor_version=2,
    )
    sibling_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_connect_zbt2.os.path.exists",
        return_value=True,
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(active_entry.entry_id) is not None
    assert hass.config_entries.async_get_entry(sibling_entry.entry_id) is None
    assert active_entry.minor_version == 2
    assert active_entry.unique_id == serial_number


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
    assert await async_setup_component(hass, USB_DOMAIN, {"usb": {}})

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
