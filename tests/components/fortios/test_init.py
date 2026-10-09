"""Test FortiOS legacy migration and authentication failures."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from aiofortiosapi import FortiOSAuthenticationError, FortiOSConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.device_tracker.legacy import Device
from homeassistant.components.fortios.client import FortiOSDevice
from homeassistant.components.fortios.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MAC, USER_INPUT

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize("failure_method", ["connect", "update"])
async def test_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    failure_method: str,
) -> None:
    """Invalid authentication requests a replacement token."""
    getattr(mock_client, failure_method).side_effect = FortiOSAuthenticationError
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        hass.config_entries.flow.async_progress()[0]["context"]["source"]
        == SOURCE_REAUTH
    )


@pytest.mark.usefixtures("mock_device_tracker_conf")
@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (FortiOSAuthenticationError(), "invalid_auth"),
        (FortiOSConnectionError(), "cannot_connect"),
    ],
)
async def test_yaml_import_failure(
    hass: HomeAssistant,
    mock_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    exception: Exception,
    reason: str,
) -> None:
    """Failed YAML import produces a repair without instructing users to delete config."""
    mock_client.connect.side_effect = exception
    assert await async_setup_component(
        hass, "device_tracker", {"device_tracker": {CONF_PLATFORM: DOMAIN} | USER_INPUT}
    )
    await hass.async_block_till_done()
    issue = issue_registry.async_get_issue(DOMAIN, f"yaml_import_{reason}")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert (
        issue_registry.async_get_issue("homeassistant", f"deprecated_yaml_{DOMAIN}")
        is None
    )


@pytest.mark.usefixtures("mock_client")
async def test_legacy_conflict(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Warn about matching tracked legacy entries and remove the issue on unload."""
    legacy = [
        Device(hass, timedelta(0), True, "old_phone", MAC),
        Device(hass, timedelta(0), False, "untracked", MAC),
    ]
    with patch(
        "homeassistant.components.fortios.async_load_config", return_value=legacy
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    issue_id = f"legacy_known_devices_{mock_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_placeholders["devices"] == "- `old_phone`"
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_yaml_import_success(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Import the grace period and use integration-owned polling."""
    config = {
        CONF_PLATFORM: DOMAIN,
        "consider_home": 300,
        "interval_seconds": 60,
    } | USER_INPUT
    assert await async_setup_component(
        hass, "device_tracker", {"device_tracker": config}
    )
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data["consider_home"] == 300
    assert "scan_interval" not in entry.data
    assert "interval_seconds" not in entry.data
    assert entry.runtime_data.consider_home == 300
    assert mock_client.update.call_count == 1
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_client.update.call_count == 2
    assert (
        issue_registry.async_get_issue("homeassistant", f"deprecated_yaml_{DOMAIN}")
        is not None
    )


async def test_unload_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Report failed platform unload without discarding runtime data."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD


async def test_late_legacy_conflict(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Devices discovered after an empty first scan also receive migration repairs."""
    legacy = [Device(hass, timedelta(0), True, "late_phone", MAC)]
    mock_client.update.return_value = {}
    with patch(
        "homeassistant.components.fortios.async_load_config", return_value=legacy
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert (
            issue_registry.async_get_issue(
                DOMAIN, f"legacy_known_devices_{mock_config_entry.entry_id}"
            )
            is None
        )
        mock_client.update.return_value = {MAC: FortiOSDevice(MAC, "phone", True)}
        freezer.tick(timedelta(seconds=12))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"legacy_known_devices_{mock_config_entry.entry_id}"
        )
        is not None
    )


async def test_fixed_polling_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ignore a scan interval stored by an earlier migration implementation."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data=mock_config_entry.data | {"scan_interval": 60}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_client.update.call_count == 1
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_client.update.call_count == 2
