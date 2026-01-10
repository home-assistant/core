"""Tests for BTHome repair handling."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.bthome import get_encryption_issue_id
from homeassistant.components.bthome.const import CONF_BINDKEY, DOMAIN
import homeassistant.components.bthome.repairs as bthome_repairs
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from . import PRST_SERVICE_INFO, TEMP_HUMI_ENCRYPTED_SERVICE_INFO

from tests.common import MockConfigEntry

BINDKEY = "231d39c1d7cc1ab1aee224cd096db932"


async def _setup_entry(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, Callable[[object, BluetoothChange], None]]:
    """Set up a BTHome config entry and capture the Bluetooth callback."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:48:E6:8F:80:A5",
        title="Test Device",
        data={CONF_BINDKEY: BINDKEY},
    )
    entry.add_to_hass(hass)

    saved_callback: Callable[[object, BluetoothChange], None] | None = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert saved_callback is not None
    return entry, saved_callback


async def test_encryption_downgrade_blocks_data_and_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test unencrypted payloads trigger an issue and stop updates."""
    entry, callback = await _setup_entry(hass)

    callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    issue_id = f"encryption_removed_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert entry.runtime_data.encryption_downgrade_logged is False

    callback(PRST_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.data is not None
    assert issue.data["entry_id"] == entry.entry_id
    assert issue.is_fixable is True
    assert entry.runtime_data.encryption_downgrade_logged is True


async def test_blocking_persists_when_issue_already_exists(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we keep blocking without spamming warnings when issue already exists."""
    entry, callback = await _setup_entry(hass)

    issue_id = f"encryption_removed_{entry.entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="encryption_removed",
        translation_placeholders={"name": entry.title},
        data={"entry_id": entry.entry_id},
    )
    entry.runtime_data.encryption_downgrade_logged = False

    with patch("homeassistant.components.bthome._LOGGER.warning") as mock_warning:
        callback(PRST_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
        await hass.async_block_till_done()
        mock_warning.assert_not_called()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
    assert entry.runtime_data.encryption_downgrade_logged is True


async def test_auto_clear_issue_when_encryption_resumes(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test encrypted payloads delete the repair issue and reset flags."""
    entry, callback = await _setup_entry(hass)

    issue_id = f"encryption_removed_{entry.entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="encryption_removed",
        translation_placeholders={"name": entry.title},
        data={"entry_id": entry.entry_id},
    )
    entry.runtime_data.encryption_downgrade_logged = True

    with patch("homeassistant.components.bthome._LOGGER.info") as mock_info:
        callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
        await hass.async_block_till_done()
        mock_info.assert_called_once()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert entry.runtime_data.encryption_downgrade_logged is False


async def test_repair_flow_removes_bindkey_and_reloads_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair flow clears the bindkey and reloads the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:48:E6:8F:80:A5",
        title="Test Device",
        data={CONF_BINDKEY: BINDKEY},
    )
    entry.add_to_hass(hass)

    issue_id = f"encryption_removed_{entry.entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="encryption_removed",
        translation_placeholders={"name": entry.title},
        data={"entry_id": entry.entry_id},
    )

    reload_mock = AsyncMock()
    with patch.object(hass.config_entries, "async_reload", reload_mock):
        flow = await bthome_repairs.async_create_fix_flow(
            hass, issue_id, {"entry_id": entry.entry_id}
        )
        flow.hass = hass
        result = await flow.async_step_init()
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await flow.async_step_confirm(user_input={})
        assert result["type"] == FlowResultType.CREATE_ENTRY

    assert CONF_BINDKEY not in entry.data
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    reload_mock.assert_awaited_once_with(entry.entry_id)


async def test_repair_flow_aborts_when_entry_removed(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair flow aborts gracefully when entry is removed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:48:E6:8F:80:A5",
        title="Test Device",
        data={CONF_BINDKEY: BINDKEY},
    )
    entry.add_to_hass(hass)

    issue_id = get_encryption_issue_id(entry.entry_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="encryption_removed",
        translation_placeholders={"name": entry.title},
        data={"entry_id": entry.entry_id},
    )

    flow = await bthome_repairs.async_create_fix_flow(
        hass, issue_id, {"entry_id": entry.entry_id}
    )
    flow.hass = hass

    # Remove entry before confirming
    await hass.config_entries.async_remove(entry.entry_id)

    result = await flow.async_step_init()
    assert result["type"] == FlowResultType.FORM

    result = await flow.async_step_confirm(user_input={})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "entry_removed"
