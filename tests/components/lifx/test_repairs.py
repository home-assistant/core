"""Tests for LIFX repairs."""

from homeassistant.components.lifx import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import IP_ADDRESS

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

MALFORMED_UNIQUE_ID = "gg:bb:cc:dd:ee:cc"


async def _setup_malformed_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry whose stored serial cannot be migrated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen",
        version=1,
        unique_id=MALFORMED_UNIQUE_ID,
        data={CONF_HOST: IP_ADDRESS},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    return entry


async def test_invalid_serial_fix_flow_removes_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the invalid serial repair removes the entry it was raised for."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await _setup_malformed_entry(hass)
    issue_id = f"invalid_serial_{entry.entry_id}"

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {
        "title": "Kitchen",
        "unique_id": MALFORMED_UNIQUE_ID,
    }

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, data["flow_id"])
    await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_removing_entry_deletes_invalid_serial_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test deleting the entry by hand also clears its repair issue."""
    entry = await _setup_malformed_entry(hass)
    issue_id = f"invalid_serial_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
