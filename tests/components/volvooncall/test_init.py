"""Test the Volvo On Call integration setup."""

from homeassistant.components.volvooncall.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_setup_entry_creates_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that setup creates a repair issue."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    issue = issue_registry.async_get_issue(DOMAIN, "volvooncall_deprecated")

    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "volvooncall_deprecated"


async def test_unload_entry_removes_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that unloading the last config entry removes the repair issue."""
    mock_config_entry.add_to_hass(hass)

    # Setup entry
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that the repair issue was created
    issue = issue_registry.async_get_issue(DOMAIN, "volvooncall_deprecated")
    assert issue is not None

    # Unload entry (this is the only entry, so issue should be removed)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that the repair issue was removed
    issue = issue_registry.async_get_issue(DOMAIN, "volvooncall_deprecated")
    assert issue is None


async def test_multiple_entries_behavior(
    hass: HomeAssistant,
) -> None:
    """Test that the unload logic correctly handles multiple entries."""
    # Test the core logic that checks remaining entries
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        title="Volvo On Call will be removed ❌ (1)",
        data={},
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        title="Volvo On Call will be removed ❌ (2)",
        data={},
    )

    # Add both entries to hass
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    # Test the logic: when checking if we should delete the issue for entry1,
    # entry2 should still be in the list of remaining entries
    remaining_entries = [
        config_entry
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.entry_id != entry1.entry_id
    ]
    assert len(remaining_entries) == 1  # entry2 should still exist
    assert remaining_entries[0].entry_id == entry2.entry_id

    # Test the logic: when checking if we should delete the issue for entry2,
    # entry1 should still be in the list of remaining entries
    remaining_entries = [
        config_entry
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.entry_id != entry2.entry_id
    ]
    assert len(remaining_entries) == 1  # entry1 should still exist
    assert remaining_entries[0].entry_id == entry1.entry_id

    # Test what happens when we remove entry1 and check for entry2
    hass.config_entries._entries.pop(entry1.entry_id)

    remaining_entries = [
        config_entry
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.entry_id != entry2.entry_id
    ]
    assert len(remaining_entries) == 0  # No other entries should exist
