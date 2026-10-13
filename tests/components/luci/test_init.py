"""Tests for the luci integration."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.legacy import Device
from homeassistant.components.luci.const import DOMAIN, ISSUE_LEGACY_KNOWN_DEVICES
from homeassistant.components.luci.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MOCK_DEVICE_1, MOCK_DEVICE_2, MOCK_DEVICE_3

from tests.common import MockConfigEntry, async_fire_time_changed

YAML_CONFIG = {
    DEVICE_TRACKER_DOMAIN: {
        CONF_PLATFORM: DOMAIN,
        CONF_HOST: "192.168.1.1",
        CONF_USERNAME: "root",
        CONF_PASSWORD: "password",
    }
}


def _issue_id(entry_id: str) -> str:
    """Return the per-entry issue ID for the legacy known_devices repair."""
    return f"{ISSUE_LEGACY_KNOWN_DEVICES}_{entry_id}"


@pytest.mark.usefixtures("mock_luci_client")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
) -> None:
    """Test setup fails with ConfigEntryNotReady on connection error."""
    mock_luci_client.is_logged_in.side_effect = RequestsConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
) -> None:
    """Test setup fails with ConfigEntryAuthFailed and starts a reauth flow."""
    mock_luci_client.is_logged_in.return_value = False

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_yaml_import_invalid_auth(
    hass: HomeAssistant,
    mock_luci_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing YAML config creates an issue on invalid auth."""
    mock_luci_client.is_logged_in.return_value = False

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_invalid_auth")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.1.1"}


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_yaml_import_cannot_connect(
    hass: HomeAssistant,
    mock_luci_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing YAML config creates an issue on connection failure."""
    mock_luci_client.is_logged_in.side_effect = RequestsConnectionError

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.1.1"}


@pytest.mark.usefixtures("mock_luci_client")
async def test_legacy_known_devices_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an issue is raised for known_devices.yaml entries we now track."""
    legacy_devices = [
        Device(hass, timedelta(0), True, "router_phone", MOCK_DEVICE_2.mac),
        Device(hass, timedelta(0), True, "homeserver", MOCK_DEVICE_1.mac),
    ]

    with patch(
        "homeassistant.components.luci.async_load_config",
        return_value=legacy_devices,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, _issue_id(mock_config_entry.entry_id)
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {
        "host": "192.168.1.1",
        "path": "known_devices.yaml",
        "devices": "- `homeserver`\n- `router_phone`",
    }


@pytest.mark.usefixtures("mock_luci_client")
async def test_legacy_known_devices_no_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test untracked and unrelated known_devices.yaml entries are ignored."""
    legacy_devices = [
        Device(hass, timedelta(0), False, "homeserver", MOCK_DEVICE_1.mac),
        Device(hass, timedelta(0), True, "other_router_device", "99:99:99:99:99:99"),
    ]

    with patch(
        "homeassistant.components.luci.async_load_config",
        return_value=legacy_devices,
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
    mock_luci_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the issue is raised for a device that only shows up after setup."""
    mock_luci_client.get_all_connected_devices.return_value = [MOCK_DEVICE_1]
    legacy_devices = [
        Device(hass, timedelta(0), True, "late_arrival", MOCK_DEVICE_3.mac),
    ]

    with patch(
        "homeassistant.components.luci.async_load_config",
        return_value=legacy_devices,
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

        mock_luci_client.get_all_connected_devices.return_value = [
            MOCK_DEVICE_1,
            MOCK_DEVICE_3,
        ]
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        # The scheduled coordinator refresh is a background task.
        await hass.async_block_till_done(wait_background_tasks=True)

    issue = issue_registry.async_get_issue(
        DOMAIN, _issue_id(mock_config_entry.entry_id)
    )
    assert issue is not None
    assert issue.translation_placeholders == {
        "host": "192.168.1.1",
        "path": "known_devices.yaml",
        "devices": "- `late_arrival`",
    }


async def test_legacy_known_devices_issue_not_recreated_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a check still running when the entry unloads cannot recreate the issue."""
    legacy_devices = [
        Device(hass, timedelta(0), True, "late_arrival", MOCK_DEVICE_3.mac),
    ]
    release_load = asyncio.Event()
    calls = 0

    async def _load_config(
        path: str, hass: HomeAssistant, consider_home: timedelta
    ) -> list[Device]:
        nonlocal calls
        calls += 1
        # Let the check during setup finish, but leave the later one suspended.
        if calls > 1:
            await release_load.wait()
        return legacy_devices

    mock_luci_client.get_all_connected_devices.return_value = [MOCK_DEVICE_1]

    with patch(
        "homeassistant.components.luci.async_load_config", side_effect=_load_config
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Released while unloading, after the integration deleted its issue.
        mock_config_entry.async_on_unload(release_load.set)

        # A conflicting MAC starts a check that blocks before it can raise.
        coordinator = mock_config_entry.runtime_data
        coordinator.async_set_updated_data(
            {MOCK_DEVICE_1.mac: MOCK_DEVICE_1, MOCK_DEVICE_3.mac: MOCK_DEVICE_3}
        )

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry.entry_id))
        is None
    )


async def test_legacy_known_devices_issue_per_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a second router without conflicts keeps the first router's issue."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JBVVVJ87F6G5V0QJX6HBC94U",
        data={
            CONF_HOST: "192.168.2.1",
            CONF_USERNAME: "root",
            CONF_PASSWORD: "password",
        },
    )
    legacy_devices = [
        Device(hass, timedelta(0), True, "homeserver", MOCK_DEVICE_1.mac),
    ]

    with patch(
        "homeassistant.components.luci.async_load_config",
        return_value=legacy_devices,
    ):
        mock_luci_client.get_all_connected_devices.return_value = [MOCK_DEVICE_1]
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # The second router tracks a device with no known_devices.yaml entry.
        mock_luci_client.get_all_connected_devices.return_value = [MOCK_DEVICE_3]
        other_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(other_entry.entry_id)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, _issue_id(mock_config_entry.entry_id)
    )
    assert issue is not None
    assert issue.translation_placeholders == {
        "host": "192.168.1.1",
        "path": "known_devices.yaml",
        "devices": "- `homeserver`",
    }
    assert (
        issue_registry.async_get_issue(DOMAIN, _issue_id(other_entry.entry_id)) is None
    )
