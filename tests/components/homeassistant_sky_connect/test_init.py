"""Test the Home Assistant SkyConnect integration."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant_hardware.repair_helpers import (
    ISSUE_MULTI_PAN_MIGRATION,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.components.homeassistant_sky_connect.const import (
    DESCRIPTION,
    DOMAIN,
    MANUFACTURER,
    PID,
    PRODUCT,
    SERIAL_NUMBER,
    VID,
)
from homeassistant.components.usb import DOMAIN as USB_DOMAIN, USBDevice
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.usb import async_request_scan, patch_scanned_serial_ports
from tests.components.usb.conftest import force_usb_polling_watcher  # noqa: F401


async def test_config_entry_migration_v2(hass: HomeAssistant) -> None:
    """Test migrating config entries from v1 to v2 format."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "device": (
                "/dev/serial/by-id/"
                "usb-Nabu_Casa_SkyConnect_v1.0"
                "_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
            ),
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
            device=(
                "/dev/serial/by-id/"
                "usb-Nabu_Casa_SkyConnect_v1.0"
                "_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
            ),
            firmware_version=None,
            firmware_type=ApplicationType.SPINEL,
            source="otbr",
            owners=[],
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.version == 1
    assert config_entry.minor_version == 5
    assert config_entry.unique_id == "3c0ed67c628beb11b1cd64a0f320645d"
    assert config_entry.data == {
        "description": "SkyConnect v1.0",
        "device": (
            "/dev/serial/by-id/"
            "usb-Nabu_Casa_SkyConnect_v1.0"
            "_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
        ),
        "vid": "10C4",
        "pid": "EA60",
        "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
        "manufacturer": "Nabu Casa",
        "product": "SkyConnect v1.0",  # `description` has been copied to `product`
        "firmware": "spinel",  # new key
        "firmware_version": None,  # new key
    }

    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    ("older", "newer", "serial_number"),
    [
        # Same physical dongle, different unique IDs
        (
            {
                "unique_id": (
                    "10C4:EA60_9e2adbd75b8beb119fe564a0f320645d_Nabu Casa"
                    "_SkyConnect v1.0 - Nabu Casa SkyConnect"
                ),
                "source": "usb",
                "data": {
                    "description": "SkyConnect v1.0",
                    "device": (
                        "/dev/serial/by-id/"
                        "usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
                    ),
                    "vid": "10C4",
                    "pid": "EA60",
                    "serial_number": "9e2adbd75b8beb119fe564a0f320645d",
                    "manufacturer": "Nabu Casa",
                    "product": "SkyConnect v1.0 - Nabu Casa SkyConnect",
                    "firmware": "ezsp",
                    "firmware_version": "7.4.4.0",
                },
            },
            {
                "unique_id": (
                    "10C4:EA60_9e2adbd75b8beb119fe564a0f320645d"
                    "_Nabu Casa_SkyConnect v1.0"
                ),
                "source": "import",
                "data": {
                    "description": "SkyConnect v1.0",
                    "device": (
                        "/dev/serial/by-id/"
                        "usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
                    ),
                    "vid": "10C4",
                    "pid": "EA60",
                    "serial_number": "9e2adbd75b8beb119fe564a0f320645d",
                    "manufacturer": "Nabu Casa",
                    "product": "SkyConnect v1.0",
                    "firmware": "ezsp",
                    "firmware_version": "7.4.4.0",
                },
            },
            "9e2adbd75b8beb119fe564a0f320645d",
        ),
        # Two entries with identical unique IDs for the same dongle
        (
            {
                "unique_id": (
                    "10C4:EA60_3c0ed67c628beb11b1cd64a0f320645d"
                    "_Nabu_Casa_SkyConnect v1.0"
                ),
                "source": "usb",
                "data": {
                    "description": "SkyConnect v1.0",
                    "device": (
                        "/dev/serial/by-id/"
                        "usb-Nabu_Casa_SkyConnect_v1.0_3c0ed67c628beb11b1cd64a0f320645d-if00-port0"
                    ),
                    "vid": "10C4",
                    "pid": "EA60",
                    "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
                    "manufacturer": "Nabu Casa",
                    "product": "SkyConnect v1.0",
                    "firmware": "ezsp",
                    "firmware_version": "7.4.4.0",
                },
            },
            {
                "unique_id": (
                    "10C4:EA60_3c0ed67c628beb11b1cd64a0f320645d"
                    "_Nabu_Casa_SkyConnect v1.0"
                ),
                "source": "import",
                "data": {
                    "description": "SkyConnect v1.0",
                    "device": (
                        "/dev/serial/by-id/"
                        "usb-Nabu_Casa_SkyConnect_v1.0_3c0ed67c628beb11b1cd64a0f320645d-if00-port0"
                    ),
                    "vid": "10C4",
                    "pid": "EA60",
                    "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
                    "manufacturer": "Nabu Casa",
                    "product": "SkyConnect v1.0",
                    "firmware": "spinel",
                    "firmware_version": "SL-OPENTHREAD/2.7.2.0_GitHub-fb0446f53; EFR32",
                },
            },
            "3c0ed67c628beb11b1cd64a0f320645d",
        ),
    ],
)
async def test_config_entry_migration_v5_collapses_duplicates(
    hass: HomeAssistant,
    older: dict,
    newer: dict,
    serial_number: str,
) -> None:
    """Test that v1.5 migration removes duplicate entries sharing a serial number."""

    older_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=older["unique_id"],
        source=older["source"],
        data=older["data"],
        version=1,
        minor_version=4,
    )
    older_entry.add_to_hass(hass)

    newer_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=newer["unique_id"],
        source=newer["source"],
        data=newer["data"],
        version=1,
        minor_version=4,
    )
    newer_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_sky_connect.os.path.exists",
        return_value=True,
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    remaining = hass.config_entries.async_entries(DOMAIN)
    assert len(remaining) == 1
    unique_entry = remaining[0]
    assert unique_entry.entry_id == newer_entry.entry_id
    assert unique_entry.minor_version == 5
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
async def test_config_entry_migration_v5_prefers_active_entry(
    hass: HomeAssistant,
    sibling_source: str,
    sibling_disabled_by: ConfigEntryDisabler | None,
) -> None:
    """Test v1.5 migration prefers an active entry over ignored/disabled siblings."""
    serial_number = "9e2adbd75b8beb119fe564a0f320645d"
    active_data = {
        "description": "SkyConnect v1.0",
        "device": (
            "/dev/serial/by-id/"
            "usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
        ),
        "vid": "10C4",
        "pid": "EA60",
        "serial_number": serial_number,
        "manufacturer": "Nabu Casa",
        "product": "SkyConnect v1.0",
        "firmware": "ezsp",
        "firmware_version": "7.4.4.0",
    }

    active_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=(
            "10C4:EA60_9e2adbd75b8beb119fe564a0f320645d_Nabu Casa_SkyConnect v1.0"
        ),
        source="usb",
        data=active_data,
        version=1,
        minor_version=4,
    )
    active_entry.add_to_hass(hass)

    sibling_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=serial_number,
        source=sibling_source,
        disabled_by=sibling_disabled_by,
        data=dict(active_data),
        version=1,
        minor_version=5,
    )
    sibling_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_sky_connect.os.path.exists",
        return_value=True,
    ):
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(active_entry.entry_id) is not None
    assert hass.config_entries.async_get_entry(sibling_entry.entry_id) is None
    assert active_entry.minor_version == 5
    assert active_entry.unique_id == serial_number


async def test_setup_fails_on_missing_usb_port(hass: HomeAssistant) -> None:
    """Test setup failing when the USB port is missing."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "description": "SkyConnect v1.0",
            "device": (
                "/dev/serial/by-id/"
                "usb-Nabu_Casa_SkyConnect_v1.0"
                "_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
            ),
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
    assert await async_setup_component(hass, USB_DOMAIN, {"usb": {}})

    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "description": "SkyConnect v1.0",
            "device": (
                "/dev/serial/by-id/"
                "usb-Nabu_Casa_SkyConnect_v1.0"
                "_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
            ),
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
                    device=(
                        "/dev/serial/by-id/"
                        "usb-Nabu_Casa_SkyConnect_v1.0"
                        "_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
                    ),
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

        # Unplug the stick before advancing time: the forced polling watcher rescans on
        # the time jump used to cool off the request debouncer, so the device must
        # already be gone or that scan would reload it as still present
        mock_exists.return_value = False

        with patch_scanned_serial_ports(return_value=[]):
            # Wait for a bit for the USB scan debouncer to cool off
            async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=5))
            await async_request_scan(hass)

        # The integration has reloaded and is now in a failed state
        await hass.async_block_till_done(wait_background_tasks=True)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_bad_config_entry_fixing(hass: HomeAssistant) -> None:
    """Test fixing/deleting config entries with bad data."""

    # Newly-added ZBT-1
    new_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id-9e2adbd75b8beb119fe564a0f320645d",
        data={
            "device": (
                "/dev/serial/by-id/"
                "usb-Nabu_Casa_SkyConnect_v1.0"
                "_9e2adbd75b8beb119fe564a0f320645d-if00-port0"
            ),
            "vid": "10C4",
            "pid": "EA60",
            "serial_number": "9e2adbd75b8beb119fe564a0f320645d",
            "manufacturer": "Nabu Casa",
            "product": "SkyConnect v1.0",
            "firmware": "ezsp",
            "firmware_version": "7.4.4.0 (build 123)",
        },
        version=1,
        minor_version=3,
    )

    new_entry.add_to_hass(hass)

    # Old config entry, without firmware info
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id-3c0ed67c628beb11b1cd64a0f320645d",
        data={
            "device": (
                "/dev/serial/by-id/"
                "usb-Nabu_Casa_SkyConnect_v1.0"
                "_3c0ed67c628beb11b1cd64a0f320645d-if00-port0"
            ),
            "vid": "10C4",
            "pid": "EA60",
            "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
            "manufacturer": "Nabu Casa",
            "description": "SkyConnect v1.0",
        },
        version=1,
        minor_version=1,
    )

    old_entry.add_to_hass(hass)

    # Bad config entry, missing most keys
    bad_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id-9f6c4bba657cc9a4f0cea48bc5948562",
        data={
            "device": (
                "/dev/serial/by-id/"
                "usb-Nabu_Casa_SkyConnect_v1.0"
                "_9f6c4bba657cc9a4f0cea48bc5948562-if00-port0"
            ),
        },
        version=1,
        minor_version=2,
    )

    bad_entry.add_to_hass(hass)

    # Bad config entry, missing most keys, but fixable since the device is present
    fixable_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id-4f5f3b26d59f8714a78b599690741999",
        data={
            "device": (
                "/dev/serial/by-id/"
                "usb-Nabu_Casa_SkyConnect_v1.0"
                "_4f5f3b26d59f8714a78b599690741999-if00-port0"
            ),
        },
        version=1,
        minor_version=2,
    )

    fixable_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_scan_serial_ports",
        return_value=[
            USBDevice(
                device="/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_4f5f3b26d59f8714a78b599690741999-if00-port0",
                vid="10C4",
                pid="EA60",
                serial_number="4f5f3b26d59f8714a78b599690741999",
                manufacturer="Nabu Casa",
                description="SkyConnect v1.0",
            )
        ],
    ):
        await async_setup_component(hass, "homeassistant_sky_connect", {})

    assert hass.config_entries.async_get_entry(new_entry.entry_id) is not None
    assert hass.config_entries.async_get_entry(old_entry.entry_id) is not None
    assert hass.config_entries.async_get_entry(fixable_entry.entry_id) is not None

    updated_entry = hass.config_entries.async_get_entry(fixable_entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.minor_version == 5
    assert updated_entry.unique_id == "4f5f3b26d59f8714a78b599690741999"
    assert updated_entry.data[VID] == "10C4"
    assert updated_entry.data[PID] == "EA60"
    assert updated_entry.data[SERIAL_NUMBER] == "4f5f3b26d59f8714a78b599690741999"
    assert updated_entry.data[MANUFACTURER] == "Nabu Casa"
    assert updated_entry.data[PRODUCT] == "SkyConnect v1.0"
    assert updated_entry.data[DESCRIPTION] == "SkyConnect v1.0"

    migrated_new_entry = hass.config_entries.async_get_entry(new_entry.entry_id)
    assert migrated_new_entry is not None
    assert migrated_new_entry.minor_version == 5
    assert migrated_new_entry.unique_id == "9e2adbd75b8beb119fe564a0f320645d"

    untouched_bad_entry = hass.config_entries.async_get_entry(bad_entry.entry_id)
    assert untouched_bad_entry.minor_version == 3


def _multi_pan_sky_connect_entry(firmware: str) -> MockConfigEntry:
    """Return a SkyConnect config entry with the given firmware type."""
    return MockConfigEntry(
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
            "firmware": firmware,
            "firmware_version": None,
        },
        title="Home Assistant SkyConnect",
        version=1,
        minor_version=4,
    )


async def test_multi_pan_migration_issue_not_created_for_cpc(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test no repair issue is created for CPC firmware when the addon is not running."""
    config_entry = _multi_pan_sky_connect_entry(ApplicationType.CPC.value)
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.os.path.exists",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.multi_pan_addon_using_device",
            return_value=False,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"{ISSUE_MULTI_PAN_MIGRATION}_{config_entry.entry_id}",
        )
        is None
    )


async def test_multi_pan_migration_issue_created_for_addon(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the repair issue is created when the multi-PAN addon is running."""
    config_entry = _multi_pan_sky_connect_entry(ApplicationType.SPINEL.value)
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.os.path.exists",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.multi_pan_addon_using_device",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=f"{ISSUE_MULTI_PAN_MIGRATION}_{config_entry.entry_id}",
    )
    assert issue is not None
    assert issue.translation_key == ISSUE_MULTI_PAN_MIGRATION
    assert issue.translation_placeholders == {
        "hardware_name": "Home Assistant SkyConnect"
    }
    assert issue.data == {"entry_id": config_entry.entry_id}
    assert issue.is_fixable


async def test_multi_pan_migration_issue_deleted_for_ezsp(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the multi-PAN migration repair issue is removed when not using multi-PAN."""
    config_entry = _multi_pan_sky_connect_entry(ApplicationType.EZSP.value)
    config_entry.add_to_hass(hass)

    ir.async_create_issue(
        hass,
        domain=DOMAIN,
        issue_id=f"{ISSUE_MULTI_PAN_MIGRATION}_{config_entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_MULTI_PAN_MIGRATION,
        translation_placeholders={"hardware_name": "Home Assistant SkyConnect"},
        data={"entry_id": config_entry.entry_id},
    )

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.os.path.exists",
            return_value=True,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.multi_pan_addon_using_device",
            return_value=False,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(
            domain=DOMAIN,
            issue_id=f"{ISSUE_MULTI_PAN_MIGRATION}_{config_entry.entry_id}",
        )
        is None
    )
