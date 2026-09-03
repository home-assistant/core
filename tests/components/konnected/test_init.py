"""Tests for the Konnected.io component."""

from homeassistant.components.konnected import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_konnected_repair_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the Konnected.io configuration entry loading/unloading handles the repair."""
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


async def test_konnected_yaml_repair_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the repair issue is created when YAML configuration is present."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, DOMAIN)
