"""Tests for the Sun WEG integration."""

from homeassistant.components.sunweg import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_sunweg_repair_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the Sun WEG configuration entry loading/unloading handles the repair."""
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

    # Add an ignored entry
    config_entry_3 = MockConfigEntry(
        source=SOURCE_IGNORE,
        domain=DOMAIN,
    )
    config_entry_3.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_3.entry_id)
    await hass.async_block_till_done()

    assert config_entry_3.state is ConfigEntryState.NOT_LOADED

    # Add a disabled entry
    config_entry_4 = MockConfigEntry(
        disabled_by=ConfigEntryDisabler.USER,
        domain=DOMAIN,
    )
    config_entry_4.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_4.entry_id)
    await hass.async_block_till_done()

    assert config_entry_4.state is ConfigEntryState.NOT_LOADED

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

    # Check the ignored and disabled entries are removed
    assert not hass.config_entries.async_entries(DOMAIN)
