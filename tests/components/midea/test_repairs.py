"""Tests for Midea repairs."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType

from homeassistant.components.midea.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import DummyDevice, SetDeviceAttribute

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


async def test_full_dust_issue_tracks_device_state(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    set_device_attribute: SetDeviceAttribute,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test full_dust creates and clears a repair issue."""
    device = DummyDevice(DeviceType.AC, attributes={"full_dust": False})
    device.is_filter_reset_supported = True
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, config_entry, device)

    issue_id = f"full_dust_{config_entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    await set_device_attribute(device, "full_dust", True)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.data == {"entry_id": config_entry.entry_id}

    await set_device_attribute(device, "full_dust", False)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    await set_device_attribute(device, "full_dust", True)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_full_dust_repair_resets_filter_after_confirmation(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    set_device_attribute: SetDeviceAttribute,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test confirming a repair calls reset_filter and waits for device state."""
    device = DummyDevice(DeviceType.AC, attributes={"full_dust": True})
    device.is_filter_reset_supported = True
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, config_entry, device)

    issue_id = f"full_dust_{config_entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
    assert device.calls == [("connect", True), ("open",)]

    assert await async_setup_component(hass, "repairs", {})
    http_client = await hass_client()
    flow = await start_repair_fix_flow(http_client, DOMAIN, issue_id)
    result = await process_repair_fix_flow(http_client, flow["flow_id"], {})

    assert result["type"] == "abort"
    assert result["reason"] == "reset_requested"
    assert ("reset_filter",) in device.calls
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await set_device_attribute(device, "full_dust", False)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_full_dust_repair_aborts_when_entry_removed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair flow aborts when its config entry is removed."""
    device = DummyDevice(DeviceType.AC, attributes={"full_dust": True})
    device.is_filter_reset_supported = True
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, config_entry, device)

    issue_id = f"full_dust_{config_entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    assert await async_setup_component(hass, "repairs", {})
    http_client = await hass_client()
    flow = await start_repair_fix_flow(http_client, DOMAIN, issue_id)

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await process_repair_fix_flow(http_client, flow["flow_id"], {})
    assert result["type"] == "abort"
    assert result["reason"] == "entry_removed"
    assert ("reset_filter",) not in device.calls
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
