"""Tests for BTHome repair handling."""

from __future__ import annotations

from collections.abc import Callable
import logging
from unittest.mock import patch

import pytest

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.bthome import get_encryption_issue_id
from homeassistant.components.bthome.const import CONF_BINDKEY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import PRST_SERVICE_INFO, TEMP_HUMI_ENCRYPTED_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator

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


async def test_encryption_downgrade_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test unencrypted payloads create a repair issue."""
    entry, callback = await _setup_entry(hass)
    issue_id = get_encryption_issue_id(entry.entry_id)

    # Send encrypted data first to establish the device
    callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    # Send unencrypted data - should create issue
    callback(PRST_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.data is not None
    assert issue.data["entry_id"] == entry.entry_id
    assert issue.is_fixable is True


async def test_encryption_downgrade_warning_only_logged_once(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test warning is only logged once per session."""
    _, callback = await _setup_entry(hass)

    # Send encrypted data first
    callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    caplog.clear()
    # First unencrypted - should warn
    callback(PRST_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert (
        sum(
            record.levelno == logging.WARNING and "unencrypted" in record.message
            for record in caplog.records
        )
        == 1
    )

    caplog.clear()
    # Second unencrypted - should not warn again
    callback(PRST_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert not any(
        record.levelno == logging.WARNING and "unencrypted" in record.message
        for record in caplog.records
    )


async def test_issue_cleared_when_encryption_resumes(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test issue is cleared when encrypted data resumes."""
    entry, callback = await _setup_entry(hass)
    issue_id = get_encryption_issue_id(entry.entry_id)

    # Send encrypted, then unencrypted to create the issue
    callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    callback(PRST_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    # Send encrypted data again - should clear issue
    callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_repair_flow_removes_bindkey_and_reloads_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair flow clears the bindkey and reloads the entry."""
    entry, callback = await _setup_entry(hass)
    issue_id = get_encryption_issue_id(entry.entry_id)

    # Send encrypted, then unencrypted to create the issue
    callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    callback(PRST_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    assert await async_setup_component(hass, "repairs", {})
    await async_process_repairs_platforms(hass)
    http_client = await hass_client()

    # Start the repair flow
    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)
    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    # Confirm the repair
    data = await process_repair_fix_flow(http_client, flow_id, {})
    assert data["type"] == "create_entry"

    # Verify bindkey was removed and issue cleared
    assert CONF_BINDKEY not in entry.data
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_repair_flow_aborts_when_entry_removed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair flow aborts gracefully when entry is removed."""
    entry, callback = await _setup_entry(hass)
    issue_id = get_encryption_issue_id(entry.entry_id)

    # Send encrypted, then unencrypted to create the issue
    callback(TEMP_HUMI_ENCRYPTED_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    callback(PRST_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    assert await async_setup_component(hass, "repairs", {})
    await async_process_repairs_platforms(hass)
    http_client = await hass_client()

    # Start the repair flow
    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)
    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    # Remove entry before confirming
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the repair - should abort
    data = await process_repair_fix_flow(http_client, flow_id, {})
    assert data["type"] == "abort"
    assert data["reason"] == "entry_removed"
