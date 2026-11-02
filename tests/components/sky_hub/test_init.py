"""Tests for the Sky Hub integration."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.device_tracker.legacy import YAML_DEVICES, Device
from homeassistant.components.sky_hub.const import (
    DEFAULT_HOST,
    DOMAIN,
    ISSUE_LEGACY_KNOWN_DEVICES,
)
from homeassistant.components.sky_hub.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import LAPTOP, PHONE


def _issue_id(entry_id: str) -> str:
    """Return the per-entry issue ID for the legacy known_devices repair."""
    return f"{ISSUE_LEGACY_KNOWN_DEVICES}_{entry_id}"


@pytest.mark.usefixtures("mock_router")
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
    mock_router: MagicMock,
) -> None:
    """Test setup retries when the router cannot connect."""
    mock_router.success_init = False
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_router")
async def test_legacy_known_devices_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test tracked legacy devices raise a conflict issue."""
    legacy_devices = [
        Device(hass, timedelta(0), True, "laptop", LAPTOP.mac),
    ]

    with patch(
        "homeassistant.components.sky_hub.async_load_config",
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
    assert issue.is_fixable is False
    assert issue.translation_key == ISSUE_LEGACY_KNOWN_DEVICES
    assert issue.translation_placeholders == {
        "host": DEFAULT_HOST,
        "path": YAML_DEVICES,
        "devices": "- `laptop`",
    }


@pytest.mark.usefixtures("mock_router")
async def test_legacy_known_devices_no_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test untracked and unrelated known_devices.yaml entries are ignored."""
    legacy_devices = [
        Device(hass, timedelta(0), False, "laptop", LAPTOP.mac),
        Device(hass, timedelta(0), True, "other_router_device", PHONE.mac),
    ]

    with patch(
        "homeassistant.components.sky_hub.async_load_config",
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
    mock_router: MagicMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device discovered after setup raises a legacy conflict issue."""
    legacy_devices = [Device(hass, timedelta(0), True, "phone", PHONE.mac)]

    with patch(
        "homeassistant.components.sky_hub.async_load_config",
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

        mock_router.async_get_skyhub_data.return_value = [LAPTOP, PHONE]
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    issue = issue_registry.async_get_issue(
        DOMAIN, _issue_id(mock_config_entry.entry_id)
    )
    assert issue is not None
    assert issue.translation_placeholders == {
        "host": DEFAULT_HOST,
        "path": YAML_DEVICES,
        "devices": "- `phone`",
    }


@pytest.mark.usefixtures("mock_router")
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
            "host": DEFAULT_HOST,
            "path": YAML_DEVICES,
            "devices": "- `laptop`",
        },
    )

    with patch("homeassistant.components.sky_hub.async_load_config", return_value=[]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry.entry_id))
        is None
    )


@pytest.mark.usefixtures("mock_router")
async def test_legacy_known_devices_issue_removed_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test unloading removes the router's legacy conflict issue."""
    legacy_devices = [Device(hass, timedelta(0), True, "laptop", LAPTOP.mac)]

    with patch(
        "homeassistant.components.sky_hub.async_load_config",
        return_value=legacy_devices,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert (
            issue_registry.async_get_issue(
                DOMAIN, _issue_id(mock_config_entry.entry_id)
            )
            is not None
        )

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry.entry_id))
        is None
    )


async def test_legacy_known_devices_issue_per_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_router: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a second router without conflicts keeps the first router's issue."""
    other_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.0.1"})
    legacy_devices = [Device(hass, timedelta(0), True, "laptop", LAPTOP.mac)]

    with patch(
        "homeassistant.components.sky_hub.async_load_config",
        return_value=legacy_devices,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        mock_router.async_get_skyhub_data.return_value = [PHONE]
        other_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(other_entry.entry_id)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, _issue_id(mock_config_entry.entry_id)
    )
    assert issue is not None
    assert issue.translation_placeholders == {
        "host": DEFAULT_HOST,
        "path": YAML_DEVICES,
        "devices": "- `laptop`",
    }
    assert (
        issue_registry.async_get_issue(DOMAIN, _issue_id(other_entry.entry_id)) is None
    )
