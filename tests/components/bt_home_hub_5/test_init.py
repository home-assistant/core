"""Tests for the BT Home Hub 5 integration setup."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bt_home_hub_5.const import (
    DOMAIN,
    ISSUE_LEGACY_KNOWN_DEVICES,
    SCAN_INTERVAL,
)
from homeassistant.components.device_tracker.legacy import YAML_DEVICES, Device
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

MOCK_HOST = "192.168.1.254"
MAC_PHONE = "00:11:22:33:44:55"
MAC_LAPTOP = "AA:BB:CC:DD:EE:FF"
DEVICE_LIST = {MAC_PHONE: "Phone"}
LOAD_CONFIG = "homeassistant.components.bt_home_hub_5.async_load_config"
GET_DEVICELIST = "homeassistant.components.bt_home_hub_5.coordinator.get_devicelist"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a BT Home Hub 5 config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        title=f"BT Home Hub 5 ({MOCK_HOST})",
    )


def _issue_id(entry_id: str) -> str:
    """Return the per-entry issue ID for the legacy known_devices repair."""
    return f"{ISSUE_LEGACY_KNOWN_DEVICES}_{entry_id}"


@pytest.mark.parametrize(
    "router_mac",
    [
        pytest.param(MAC_PHONE, id="uppercase"),
        pytest.param(MAC_PHONE.lower(), id="lowercase"),
    ],
)
async def test_legacy_known_devices_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    router_mac: str,
) -> None:
    """Test a tracked known_devices.yaml entry for a router client raises an issue."""
    legacy_devices = [Device(hass, timedelta(0), True, "my_phone", MAC_PHONE)]

    with (
        patch(LOAD_CONFIG, return_value=legacy_devices),
        patch(GET_DEVICELIST, return_value={router_mac: "Phone"}),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, _issue_id(mock_config_entry.entry_id)
    )
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.is_fixable is False
    assert issue.translation_key == ISSUE_LEGACY_KNOWN_DEVICES
    assert issue.translation_placeholders == {
        "host": MOCK_HOST,
        "path": YAML_DEVICES,
        "devices": "- `my_phone`",
    }


async def test_legacy_known_devices_no_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test untracked and unrelated known_devices.yaml entries are ignored."""
    legacy_devices = [
        Device(hass, timedelta(0), False, "my_phone", MAC_PHONE),
        Device(hass, timedelta(0), True, "other_router_device", MAC_LAPTOP),
    ]

    with (
        patch(LOAD_CONFIG, return_value=legacy_devices),
        patch(GET_DEVICELIST, return_value=DEVICE_LIST),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry.entry_id))
        is None
    )


async def test_legacy_known_devices_issue_on_new_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device discovered after setup raises a legacy conflict issue."""
    legacy_devices = [Device(hass, timedelta(0), True, "my_laptop", MAC_LAPTOP)]

    with (
        patch(LOAD_CONFIG, return_value=legacy_devices),
        patch(GET_DEVICELIST, return_value=DEVICE_LIST) as mock_get_devicelist,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert (
            issue_registry.async_get_issue(
                DOMAIN, _issue_id(mock_config_entry.entry_id)
            )
            is None
        )

        mock_get_devicelist.return_value = {MAC_PHONE: "Phone", MAC_LAPTOP: "Laptop"}
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    issue = issue_registry.async_get_issue(
        DOMAIN, _issue_id(mock_config_entry.entry_id)
    )
    assert issue is not None
    assert issue.translation_placeholders == {
        "host": MOCK_HOST,
        "path": YAML_DEVICES,
        "devices": "- `my_laptop`",
    }


async def test_legacy_known_devices_issue_cleared(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test setup clears a previous issue when no legacy conflicts remain."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(mock_config_entry.entry_id),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_LEGACY_KNOWN_DEVICES,
        translation_placeholders={
            "host": MOCK_HOST,
            "path": YAML_DEVICES,
            "devices": "- `my_phone`",
        },
    )

    with (
        patch(LOAD_CONFIG, return_value=[]),
        patch(GET_DEVICELIST, return_value=DEVICE_LIST),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry.entry_id))
        is None
    )


async def test_legacy_known_devices_issue_kept_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test unloading keeps the router's legacy conflict issue."""
    legacy_devices = [Device(hass, timedelta(0), True, "my_phone", MAC_PHONE)]

    with (
        patch(LOAD_CONFIG, return_value=legacy_devices),
        patch(GET_DEVICELIST, return_value=DEVICE_LIST),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry.entry_id))


async def test_legacy_known_devices_issue_removed_with_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test removing the config entry removes its legacy conflict issue."""
    legacy_devices = [Device(hass, timedelta(0), True, "my_phone", MAC_PHONE)]

    with (
        patch(LOAD_CONFIG, return_value=legacy_devices),
        patch(GET_DEVICELIST, return_value=DEVICE_LIST),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry.entry_id))

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry.entry_id))
        is None
    )


async def test_unload_entry_platform_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a platform that fails to unload leaves the entry in a failed state."""
    with patch(GET_DEVICELIST, return_value=DEVICE_LIST):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
