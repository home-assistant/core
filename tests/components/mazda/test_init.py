"""Tests for the Mazda Connected Services integration."""

from homeassistant.components.mazda import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_mazda_repair_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the Mazda configuration entry loading/unloading handles the repair."""
    config_entry_1 = MockConfigEntry(
        title="Example 1",
        domain=DOMAIN,
    )
    config_entry_1.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_1.entry_id)
    await hass.async_block_till_done()
    assert config_entry_1.state is ConfigEntryState.LOADED

    # Add a second one
    config_entry_2 = MockConfigEntry(
        title="Example 2",
        domain=DOMAIN,
    )
    config_entry_2.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_2.entry_id)
    await hass.async_block_till_done()

    assert config_entry_2.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, DOMAIN)

    # Remove the first one
    await hass.config_entries.async_remove(config_entry_1.entry_id)
    await hass.async_block_till_done()

    assert config_entry_1.state is ConfigEntryState.NOT_LOADED
    assert config_entry_2.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, DOMAIN)

    # Remove the second one
    await hass.config_entries.async_remove(config_entry_2.entry_id)
    await hass.async_block_till_done()

    assert config_entry_1.state is ConfigEntryState.NOT_LOADED
    assert config_entry_2.state is ConfigEntryState.NOT_LOADED
    assert issue_registry.async_get_issue(DOMAIN, DOMAIN) is None
